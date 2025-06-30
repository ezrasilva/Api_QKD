import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import qkd_client

# Carrega as variáveis de ambiente do ficheiro .env (para desenvolvimento local)
load_dotenv()

# Inicializa as extensões fora da fábrica para que possam ser importadas noutros locais
db = SQLAlchemy()

# --- Modelo da Base de Dados com SQLAlchemy ---
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.String(80), nullable=False)
    receiver_id = db.Column(db.String(80), nullable=False)
    key_id = db.Column(db.String(255), nullable=False, unique=True)
    ciphertext_hex = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

def create_app():
    """Cria e configura a instância da aplicação Flask (Padrão de Fábrica)."""
    app = Flask(__name__)
    CORS(app)

    # --- Configuração da Base de Dados ---
    # Obtém a URL da base de dados da variável de ambiente.
    # O Render irá fornecer esta variável automaticamente.
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("A variável de ambiente DATABASE_URL não está definida.")
    
    # O Render usa 'postgres://', mas o SQLAlchemy espera 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Associa a instância da base de dados à aplicação
    db.init_app(app)

    # --- Endpoints da API ---
    @app.route('/api/send_message', methods=['POST'])
    def send_message():
        data = request.get_json()
        sender_id = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        message_text = data.get('message')
        account_id = "2577"

        if not all([sender_id, receiver_id, message_text]):
            return jsonify({"error": "Dados em falta"}), 400

        kme_number = "1" if sender_id == "sae-1" else "2"
        
        key_id, key_material_b64 = qkd_client.request_new_key(account_id, sender_id, receiver_id, kme_number)
        if not key_material_b64:
            return jsonify({"error": "Não foi possível obter a chave do serviço QKD"}), 503

        f = Fernet(key_material_b64)
        encrypted_message_hex = f.encrypt(message_text.encode('utf-8')).hex()

        new_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            key_id=key_id,
            ciphertext_hex=encrypted_message_hex
        )
        db.session.add(new_message)
        db.session.commit()
        
        return jsonify({"status": "success", "message": "Mensagem enviada e cifrada com sucesso!"})

    @app.route('/api/get_messages/<string:user_id>', methods=['GET'])
    def get_messages(user_id):
        messages_to_process = Message.query.filter_by(receiver_id=user_id, is_read=False).all()
        if not messages_to_process:
            return jsonify({"messages": []})

        decrypted_messages = []
        account_id = "2577"
        kme_number = "2" if user_id == "sae-2" else "1"

        for msg in messages_to_process:
            key_material_b64 = qkd_client.get_key_by_id(account_id, user_id, msg.sender_id, msg.key_id, kme_number)
            
            if not key_material_b64:
                decrypted_messages.append({"from": msg.sender_id, "text": f"[ERRO DE SISTEMA: Chave {msg.key_id} não obtida]"})
                continue
            
            try:
                f = Fernet(key_material_b64)
                decrypted_text = f.decrypt(bytes.fromhex(msg.ciphertext_hex)).decode('utf-8')
                decrypted_messages.append({"from": msg.sender_id, "text": decrypted_text})
                msg.is_read = True
            except Exception as e:
                decrypted_messages.append({"from": msg.sender_id, "text": f"[ERRO DE DECIFRAGEM: {e}]"})
        
        db.session.commit()
        return jsonify({"messages": decrypted_messages})

    return app

# --- Executar o Servidor ---
if __name__ == '__main__':
    app = create_app()
    # Cria as tabelas na base de dados, se não existirem
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)