import json

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .groq_client import MODEL, SYSTEM_PROMPT, get_client
from .models import Conversation, Message
from .serializers import ConversationDetailSerializer, ConversationListSerializer
from .tools import TOOL_SCHEMAS, run_tool

MAX_TOOL_HOPS = 5


@api_view(["GET"])
def health(request):
    return Response({"ok": True, "model": MODEL})


class ConversationListCreateView(generics.ListCreateAPIView):
    queryset = Conversation.objects.all()

    def get_serializer_class(self):
        return ConversationListSerializer

    def create(self, request, *args, **kwargs):
        title = (request.data.get("title") or "New chat").strip()[:255]
        convo = Conversation.objects.create(title=title or "New chat")
        return Response(
            ConversationListSerializer(convo).data, status=status.HTTP_201_CREATED
        )


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationDetailSerializer


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatStreamView(APIView):
    """
    POST /api/chat/
    Body: { "conversation_id": "<uuid>", "message": "<text>" }

    Saves the user message, runs the tool-calling agent loop against
    Groq/OpenAI, streams tokens back over SSE, then saves the assistant's
    final reply.
    """

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        user_text = (request.data.get("message") or "").strip()

        if not conversation_id or not user_text:
            return Response(
                {"error": "conversation_id and message are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation = get_object_or_404(Conversation, id=conversation_id)
        Message.objects.create(conversation=conversation, role="user", content=user_text)

        # Auto-title new conversations from the first user message.
        if conversation.messages.filter(role="user").count() == 1:
            conversation.title = (user_text[:42] + "…") if len(user_text) > 42 else user_text
            conversation.save(update_fields=["title"])

        history = [
            {"role": m.role, "content": m.content}
            for m in conversation.messages.all()
            if m.role in ("user", "assistant")
        ]

        def event_stream():
            client = get_client()
            working_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
            final_text = ""

            try:
                for hop in range(MAX_TOOL_HOPS):
                    try:
                        completion = client.chat.completions.create(
                            model=MODEL,
                            messages=working_messages,
                            tools=TOOL_SCHEMAS,
                            tool_choice="auto",
                        )
                    except Exception as tool_err:  # noqa: BLE001
                        # Some models occasionally emit a malformed function
                        # call that the provider rejects (400 tool_use_failed).
                        # Fall back to a plain, tool-less completion so the
                        # user still gets an answer instead of a crash.
                        if hop == 0:
                            yield _sse(
                                "tool_call", {"name": "retrying_without_tools"}
                            )
                        completion = client.chat.completions.create(
                            model=MODEL,
                            messages=working_messages,
                        )

                    choice = completion.choices[0]
                    msg = choice.message

                    if getattr(msg, "tool_calls", None):
                        working_messages.append(
                            {
                                "role": "assistant",
                                "content": msg.content or "",
                                "tool_calls": [
                                    {
                                        "id": tc.id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.function.name,
                                            "arguments": tc.function.arguments,
                                        },
                                    }
                                    for tc in msg.tool_calls
                                ],
                            }
                        )

                        for tc in msg.tool_calls:
                            yield _sse("tool_call", {"name": tc.function.name})
                            try:
                                args = json.loads(tc.function.arguments or "{}")
                            except json.JSONDecodeError:
                                args = {}

                            result = run_tool(tc.function.name, args)
                            yield _sse(
                                "tool_result", {"name": tc.function.name, "result": result}
                            )

                            working_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": json.dumps(result),
                                }
                            )
                        continue  # let the model see tool results and respond again

                    # No tool calls -> stream the final answer.
                    stream = client.chat.completions.create(
                        model=MODEL,
                        messages=working_messages,
                        stream=True,
                    )
                    for part in stream:
                        delta = part.choices[0].delta.content
                        if delta:
                            final_text += delta
                            yield _sse("token", {"content": delta})
                    break

                if final_text:
                    Message.objects.create(
                        conversation=conversation, role="assistant", content=final_text
                    )
                yield _sse("done", {})

            except Exception as exc:  # noqa: BLE001
                yield _sse("error", {"message": str(exc)})

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
