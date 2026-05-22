import os
import sys
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv
from typing import List, Dict

# Tìm đường dẫn tuyệt đối đến file .env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Fix đường dẫn để import được VectorDBManager
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from ai_engine.vector_db import VectorDBManager


class RAGChain:
    def __init__(self, db_manager=None):
        # 1. Kết nối VectorStore (Qdrant - Chạy local hoàn toàn)
        if db_manager:
            self.db_manager = db_manager
        else:
            self.db_manager = VectorDBManager()

        self.vector_store = self.db_manager.get_vector_store()

        # 2. Tạo Retriever để tìm 8 đoạn văn bản liên quan nhất
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 8}
        )

    def _format_docs(self, docs):
        """Làm sạch dữ liệu context để AI dễ đọc"""
        formatted_context = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "Handbook")
            content = doc.page_content
            formatted_context.append(f"--- Đoạn {i+1} (Nguồn: {source}) ---\n{content}")
        return "\n\n".join(formatted_context)

    def _format_chat_history(self, chat_history: List[Dict]) -> List[Dict]:
        """
        Chuyển lịch sử hội thoại sang định dạng Groq messages.
        chat_history: [{"question": "...", "answer": "..."}, ...]
        """
        messages = []
        for turn in chat_history:
            messages.append({"role": "user", "content": turn["question"]})
            messages.append({"role": "assistant", "content": turn["answer"]})
        return messages

    def ask(self, question: str, chat_history: List[Dict] = []):
        """
        DÙNG GROQ ĐỂ GENERATION (PHÁT NGÔN)
        chat_history: lịch sử hội thoại từ ChatService, dạng:
            [{"question": "...", "answer": "..."}, ...]
        """
        try:
            # 0. Kiểm tra nhanh lời chào xã giao đơn giản để phản hồi tức thì và không đính kèm nguồn
            q_clean = question.strip().lower().replace("?", "").replace(".", "").replace("!", "").replace(",", "")
            simple_greetings = {"hello", "hi", "chào", "chào bạn", "xin chào", "hey", "hi there", "hello there", "greetings"}
            if q_clean in simple_greetings:
                return "Xin chào! Tôi là trợ lý ảo hỗ trợ thông tin về GitLab Handbook. Tôi có thể giúp gì cho bạn hôm nay?", []

            # 1. Tìm tài liệu liên quan từ Database (Local Embedding)
            docs = self.retriever.invoke(question)
            if not docs:
                return "Tôi không tìm thấy thông tin về vấn đề này trong GitLab Handbook.", []

            context = self._format_docs(docs)
            if not context.strip():
                return "Tôi không tìm thấy thông tin về vấn đề này trong GitLab Handbook.", []

            # 2. Khởi tạo Client Groq
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return "Lỗi: Không tìm thấy GROQ_API_KEY trong file .env", []

            client = Groq(api_key=api_key)

            # 3. Build messages: system → lịch sử → câu hỏi mới
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Bạn là chuyên gia về GitLab Handbook. "
                        "Hãy trả lời bằng TIẾNG VIỆT dựa TRÊN NGỮ CẢNH ĐƯỢC CUNG CẤP dưới đây.\n"
                        "CHỈ trả lời dựa trên thông tin có trong ngữ cảnh. KHÔNG ĐƯỢC tự suy luận, tự bịa hoặc sử dụng kiến thức bên ngoài.\n"
                        "Nếu ngữ cảnh không chứa thông tin hoặc câu hỏi không liên quan đến GitLab Handbook, bạn BẮT BUỘC CHỈ ĐƯỢC trả lời duy nhất câu sau:\n"
                        "'Tôi không tìm thấy thông tin về vấn đề này trong GitLab Handbook.'\n"
                        "Đối với các câu chào hỏi xã giao hoặc hỏi thăm thông thường (ví dụ: 'hello', 'hi', 'chào bạn', 'bạn là ai',...), hãy trả lời một cách lịch sự và bắt buộc thêm tiền tố '[OFFTOPIC]' ở ngay đầu câu trả lời.\n"
                        "Ví dụ: '[OFFTOPIC] Xin chào! Tôi là trợ lý ảo hỗ trợ GitLab Handbook. Hôm nay tôi có thể giúp gì cho bạn?'\n"
                        "TUYỆT ĐỐI KHÔNG ĐƯỢC viết thêm bất kỳ thông tin tự suy luận hay kiến thức ngoài lề nào khác ngoài ngữ cảnh được cung cấp.\n\n"
                        "Nếu câu hỏi liên quan đến lịch sử hội thoại, hãy dùng context đó để trả lời nhất quán.\n\n"
                        f"Ngữ cảnh:\n{context}"
                    )
                }
            ]

            # ✅ Thêm lịch sử hội thoại vào giữa (tối đa 10 lượt gần nhất)
            if chat_history:
                messages.extend(self._format_chat_history(chat_history[-10:]))

            # ✅ Thêm câu hỏi hiện tại
            messages.append({"role": "user", "content": question})

            # 4. Gọi model Llama 3
            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.0
            )

            answer = chat_completion.choices[0].message.content
            
            # Nếu câu trả lời bắt đầu bằng tiền tố [OFFTOPIC] (câu chào xã giao)
            if answer.startswith("[OFFTOPIC]"):
                answer = answer.replace("[OFFTOPIC]", "").strip()
                docs = []
            # Nếu câu trả lời thông báo không tìm thấy thông tin trong Handbook
            elif "Tôi không tìm thấy thông tin" in answer or "không tìm thấy thông tin" in answer:
                docs = []

            return answer, docs

        except Exception as e:
            return f"Lỗi hệ thống Groq: {str(e)}", []
