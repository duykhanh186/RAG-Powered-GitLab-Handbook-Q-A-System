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
            simple_greetings = {"hello", "hi", "chào", "chào bạn", "xin chào", "hey", "hi there", "hello there", "greetings", "tạm biệt", "bye"}
            if q_clean in simple_greetings:
                return "Xin chào! Tôi là trợ lý ảo hỗ trợ thông tin về GitLab Handbook. Tôi có thể giúp gì cho bạn hôm nay?", []

            # 1. Tối ưu hóa câu hỏi tìm kiếm dựa trên lịch sử hội thoại (Query Condensation)
            search_query = self._condense_question(question, chat_history)

            # Tìm tài liệu liên quan từ Database (Local Embedding) dựa trên câu hỏi đã tối ưu hóa
            docs = self.retriever.invoke(search_query)
            if not docs:
                return "Tôi không tìm thấy thông tin này trong tài liệu GitLab Handbook. Tôi có thể giúp gì khác cho bạn không?", []

            context = self._format_docs(docs)
            if not context.strip():
                return "Tôi không tìm thấy thông tin này trong tài liệu GitLab Handbook. Tôi có thể giúp gì khác cho bạn không?", []

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
                        "Bạn là một trợ lý ảo chuyên nghiệp hỗ trợ hỏi đáp dựa trên tài liệu GitLab Handbook được cung cấp.\n"
                        "Nhiệm vụ của bạn là trả lời câu hỏi của người dùng bằng tiếng Việt theo các quy tắc nghiêm ngặt sau:\n\n"
                        "QUY TẮC PHÂN LOẠI VÀ ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:\n\n"
                        "1. CÂU HỎI XÃ GIAO, CHÀO HỎI (SOCIAL):\n"
                        "   - Dấu hiệu: Chào hỏi, chúc sức khỏe, hỏi thăm, v.v.\n"
                        "   - Quy tắc trả lời: Trả lời lại một cách lịch sự, thân thiện, ấm áp và chuyên nghiệp.\n"
                        "   - Định dạng bắt buộc: Phải bắt đầu bằng tiền tố '[SOCIAL]' ở ngay đầu câu trả lời (ví dụ: '[SOCIAL] Xin chào!...').\n"
                        "   - Tuyệt đối không kèm nguồn tài liệu hay trích dẫn nào.\n\n"
                        "2. CÂU HỎI NGOÀI LỀ HOẶC KHÔNG TÌM THẤY TRONG TÀI LIỆU (OFF-TOPIC / OUT OF CONTEXT):\n"
                        "   - Dấu hiệu: Các câu hỏi không liên quan đến GitLab Handbook, kiến thức chung (địa lý, lịch sử, toán học, lập trình chung, v.v.), hoặc câu hỏi có liên quan đến GitLab nhưng KHÔNG CÓ thông tin trong phần 'Ngữ cảnh' dưới đây để trả lời.\n"
                        "   - Quy tắc trả lời: Tuyệt đối KHÔNG sử dụng kiến thức bên ngoài của bạn để trả lời câu hỏi. Bạn BẮT BUỘC chỉ được thông báo rằng không tìm thấy thông tin trong tài liệu và hỏi xem có thể giúp gì khác cho họ.\n"
                        "   - Định dạng bắt buộc: Phải bắt đầu bằng tiền tố '[OFFTOPIC]' ở ngay đầu câu trả lời (ví dụ: '[OFFTOPIC] Tôi không tìm thấy thông tin này trong tài liệu GitLab Handbook. Tôi có thể giúp gì khác cho bạn không?').\n"
                        "   - Tuyệt đối không kèm nguồn tài liệu hay trích dẫn nào.\n\n"
                        "3. CÂU HỎI CÓ TRONG TÀI LIỆU (IN-DOCUMENT):\n"
                        "   - Dấu hiệu: Câu hỏi có đầy đủ thông tin để trả lời dựa trên phần 'Ngữ cảnh' dưới đây.\n"
                        "   - Quy tắc trả lời:\n"
                        "     - Trả lời một cách CHI TIẾT, ĐẦY ĐỦ, TOÀN DIỆN dựa strictly (hoàn toàn) vào thông tin trong phần 'Ngữ cảnh'. Không tóm tắt quá ngắn gọn làm mất đi thông tin quan trọng.\n"
                        "     - TUYỆT ĐỐI KHÔNG tự bịa đặt, suy diễn, phỏng đoán hoặc thêm bất kỳ nội dung/thông tin nào không có trong phần 'Ngữ cảnh'. Nếu ngữ cảnh không có thông tin đó, hãy xử lý theo quy tắc NGOÀI LỀ.\n"
                        "     - TUYỆT ĐỐI KHÔNG tự ý chào hỏi (không dùng 'Xin chào!', 'Chào bạn!'), chúc sức khỏe hoặc thêm các từ ngữ xã giao ở đầu câu trả lời. TUYỆT ĐỐI KHÔNG bắt chước hay lặp lại lời chào từ lịch sử chat cũ. Phải đi thẳng vào câu trả lời thực tế từ tài liệu.\n"
                        "     - Trình bày rõ ràng, dễ hiểu, sử dụng định dạng danh sách (bullet points) hoặc đánh số nếu cần thiết.\n"
                        "   - Định dạng bắt buộc: Tuyệt đối KHÔNG thêm bất kỳ tiền tố nào như '[SOCIAL]' hay '[OFFTOPIC]'. Phải đi thẳng trực tiếp vào nội dung trả lời thực tế từ tài liệu. TUYỆT ĐỐI KHÔNG giải thích, phản bác, chào hỏi lại (bỏ qua mọi lời chào trong lịch sử chat cũ) hay viết các câu giao tiếp như 'Không, tôi xin lỗi, câu hỏi này không thuộc...'.\n\n"
                        "VÍ DỤ VỀ ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:\n\n"
                        "Ví dụ 1 (Câu hỏi xã giao - SOCIAL):\n"
                        "- Người dùng: \"Chào bạn, bạn khỏe không?\"\n"
                        "- Phản hồi: \"[SOCIAL] Xin chào! Tôi là trợ lý ảo hỗ trợ GitLab Handbook. Tôi rất khỏe và sẵn sàng hỗ trợ bạn. Hôm nay tôi có thể giúp gì cho bạn?\"\n\n"
                        "Ví dụ 2 (Câu hỏi ngoài lề - OFF-TOPIC):\n"
                        "- Người dùng: \"Thủ đô của nước Pháp là gì?\"\n"
                        "- Phản hồi: \"[OFFTOPIC] Tôi không tìm thấy thông tin này trong tài liệu GitLab Handbook. Tôi có thể giúp gì khác cho bạn không?\"\n\n"
                        "Ví dụ 3 (Câu hỏi có trong tài liệu - IN-DOCUMENT):\n"
                        "- Người dùng: \"GitLab Billing Entities bao gồm những công ty nào?\"\n"
                        "- Phản hồi: \"Các thực thể hóa đơn (Billing Entities) của GitLab bao gồm:\\n- GitLab Inc ở Mỹ\\n- GitLab BV ở Hà Lan\\n- GitLab Ltd ở Anh\\n- GitLab GmbH ở Đức\\n- GitLab PTY LTD ở Úc\"\n\n"
                        "Hãy sử dụng ngữ cảnh và lịch sử hội thoại dưới đây để trả lời câu hỏi hiện tại một cách nhất quán.\n\n"
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

            # Nếu câu trả lời bắt đầu bằng tiền tố [OFFTOPIC] hoặc [SOCIAL] (câu hỏi ngoài lề / xã giao / không có trong nguồn)
            if answer.startswith("[OFFTOPIC]"):
                answer = answer.replace("[OFFTOPIC]", "").strip()
                docs = []
            elif answer.startswith("[SOCIAL]"):
                answer = answer.replace("[SOCIAL]", "").strip()
                docs = []

            return answer, docs

        except Exception as e:
            return f"Lỗi hệ thống Groq: {str(e)}", []
