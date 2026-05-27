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

    def _condense_question(self, question: str, chat_history: List[Dict]) -> str:
        """
        Dùng LLM (Groq) để chuyển câu hỏi tiếp nối (follow-up) thành một câu hỏi độc lập (standalone question)
        dựa trên lịch sử hội thoại để phục vụ việc truy vấn Vector DB chính xác hơn.
        """
        if not chat_history:
            return question

        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return question

            client = Groq(api_key=api_key)

            # Format lịch sử hội thoại ngắn gọn (tối đa 5 lượt gần nhất)
            history_str = ""
            for turn in chat_history[-5:]:
                history_str += f"User: {turn['question']}\nAssistant: {turn['answer']}\n"

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Bạn là một trợ lý thông minh hỗ trợ viết lại câu hỏi.\n"
                        "Nhiệm vụ của bạn là đọc lịch sử hội thoại (Chat History) và câu hỏi tiếp nối mới nhất (Follow-up Question),\n"
                        "sau đó tạo ra một câu hỏi độc lập (Standalone Question) đầy đủ ý nghĩa bằng tiếng Việt để tìm kiếm tài liệu tương đồng.\n\n"
                        "Quy tắc nghiêm ngặt:\n"
                        "1. KHÔNG trả lời câu hỏi, CHỈ viết lại câu hỏi dưới dạng một câu truy vấn độc lập.\n"
                        "2. Giữ nguyên ý định gốc của người dùng.\n"
                        "3. Nếu câu hỏi mới nhất đã rõ ràng, đầy đủ ý nghĩa và có thể tự hiểu được mà không cần đến lịch sử (ví dụ: 'GitLab values là gì?'), "
                        "hãy trả về chính xác câu hỏi đó mà không thay đổi.\n"
                        "4. Chỉ trả về duy nhất nội dung câu hỏi độc lập được viết lại, TUYỆT ĐỐI KHÔNG thêm bất kỳ lời giải thích, lời chào, "
                        "hoặc ký hiệu dẫn giải nào khác."
                    )
                },
                {
                    "role": "user",
                    "content": f"Chat History:\n{history_str}\nFollow-up Question: {question}\n\nStandalone Question:"
                }
            ]

            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.0
            )

            condensed = chat_completion.choices[0].message.content.strip()
            if condensed.startswith('"') and condensed.endswith('"'):
                condensed = condensed[1:-1].strip()
            if condensed.startswith("'") and condensed.endswith("'"):
                condensed = condensed[1:-1].strip()
                
            return condensed
        except Exception as e:
            return question

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

            # 1. Tối ưu hóa câu hỏi tìm kiếm dựa trên lịch sử hội thoại (Query Condensation)
            search_query = self._condense_question(question, chat_history)

            # Tìm tài liệu liên quan từ Database (Local Embedding) dựa trên câu hỏi đã tối ưu hóa
            docs = self.retriever.invoke(search_query)
            if not docs:
                return "Rất tiếc, tôi không tìm thấy tài liệu liên quan đến câu hỏi này trong nguồn GitLab Handbook. Bạn có cần hỗ trợ thêm thông tin nào khác không?", []

            context = self._format_docs(docs)
            if not context.strip():
                return "Rất tiếc, tôi không tìm thấy tài liệu liên quan đến câu hỏi này trong nguồn GitLab Handbook. Bạn có cần hỗ trợ thêm thông tin nào khác không?", []

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
                        "Bạn là một trợ lý ảo chuyên gia chỉ hỗ trợ hỏi đáp dựa trên tài liệu GitLab Handbook được cung cấp.\n"
                        "Hãy trả lời câu hỏi của người dùng bằng TIẾNG VIỆT dựa TRÊN NGỮ CẢNH (context) được cung cấp dưới đây.\n\n"
                        "QUY TẮC PHẠM VI TRẢ LỜI NGHIÊM NGẶT:\n\n"
                        "1. ĐỐI VỚI CÂU HỎI NẰM TRONG BẢN CẢNH (ON-TOPIC):\n"
                        "   - Hãy trả lời một cách CHI TIẾT, ĐẦY ĐỦ, TOÀN DIỆN và CỤ THỂ nhất có thể dựa vào thông tin trong phần 'Ngữ cảnh'. Không tóm tắt quá ngắn gọn làm mất đi các chi tiết quan trọng.\n"
                        "   - Hãy trình bày câu trả lời một cách rõ ràng, khoa học, sử dụng các dấu đầu dòng (bullet points) hoặc danh sách đánh số để phân tích các ý chính nếu ngữ cảnh chứa nhiều thông tin chi tiết.\n"
                        "   - Chỉ trả lời dựa vào thông tin CÓ SẴN trong phần 'Ngữ cảnh' dưới đây.\n"
                        "   - Trả lời trung thực, chính xác, không tự suy diễn hay thêm bớt thông tin ngoài ngữ cảnh.\n\n"
                        "2. ĐỐI VỚI CÂU HỎI LUNG TUNG, NGOÀI LỀ, KIẾN THỨC CHUNG HOẶC KHÔNG CÓ TRONG NGỮ CẢNH (OFF-TOPIC):\n"
                        "   - Nếu câu hỏi của người dùng là câu hỏi xã giao, hỏi thăm, hoặc bất kỳ câu hỏi kiến thức chung nào "
                        "(ví dụ: địa lý, khoa học, nghệ thuật, toán học, màu sắc, đời sống, lập trình, xe cộ, đèn đường...) MÀ KHÔNG CÓ thông tin trong 'Ngữ cảnh' dưới đây để trả lời:\n"
                        "     - Bạn TUYỆT ĐỐI KHÔNG ĐƯỢC dùng kiến thức của bản thân để trả lời trực tiếp câu hỏi đó (Ví dụ: Không được trả lời trực tiếp màu sắc của đèn đỏ, không được trả lời thủ đô của Pháp, v.v.).\n"
                        "     - Bạn BẮT BUỘC phải trả lời một cách cực kỳ LỊCH SỰ, THÂN THIỆN và từ tốn rằng thông tin này không có trong nguồn tài liệu GitLab Handbook.\n"
                        "     - Bạn BẮT BUỘC phải viết tiền tố '[OFFTOPIC]' ở ngay đầu câu trả lời để hệ thống ẩn nguồn tài liệu.\n"
                        "     - Ví dụ minh họa bắt buộc tuân theo:\n"
                        "       * Khách hỏi: \"đèn đỏ màu gì?\" -> Bạn trả lời: \"[OFFTOPIC] Rất tiếc, câu hỏi về màu sắc của đèn giao thông không nằm trong nguồn tài liệu GitLab Handbook. Tôi không tìm thấy thông tin này trong GitLab Handbook. Tôi có thể giúp gì cho bạn về các chính sách hay quy trình của GitLab không?\"\n"
                        "       * Khách hỏi: \"thời tiết hôm nay thế nào?\" -> Bạn trả lời: \"[OFFTOPIC] Tôi là trợ lý chuyên về GitLab Handbook và rất tiếc thông tin thời tiết không có trong nguồn tài liệu GitLab Handbook của tôi. Tôi không tìm thấy thông tin về vấn đề này trong GitLab Handbook.\"\n"
                        "       * Khách hỏi: \"bạn khỏe không?\" -> Bạn trả lời: \"[OFFTOPIC] Cảm ơn bạn đã hỏi thăm! Tôi là trợ lý ảo hỗ trợ GitLab Handbook. Rất tiếc câu hỏi xã giao này không có trong nguồn tài liệu GitLab Handbook. Bạn có cần hỗ trợ tra cứu quy trình nào của GitLab không?\"\n\n"
                        "BẤT KỲ CÂU TRẢ LỜI NÀO KHÔNG THỂ DỰA VÀO NGỮ CẢNH ĐỂ TRẢ LỜI ĐỀU PHẢI BẮT ĐẦU BẰNG TIỀN TỐ '[OFFTOPIC]'.\n\n"
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
            
            # Nếu câu trả lời bắt đầu bằng tiền tố [OFFTOPIC] (câu hỏi ngoài lề / xã giao / không có trong nguồn)
            if answer.startswith("[OFFTOPIC]"):
                answer = answer.replace("[OFFTOPIC]", "").strip()
                docs = []
            # Nếu câu trả lời thông báo không tìm thấy thông tin trong Handbook
            elif "không tìm thấy thông tin" in answer.lower() or "không nằm trong phạm vi" in answer.lower() or "không có trong nguồn" in answer.lower() or "rất tiếc" in answer.lower():
                docs = []

            return answer, docs

        except Exception as e:
            return f"Lỗi hệ thống Groq: {str(e)}", []
