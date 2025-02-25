from app import app, db
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar o banco de dados
with app.app_context():
    try:
        logger.info("Iniciando criação de tabelas...")
        db.create_all()
        logger.info("Tabelas criadas com sucesso!")
    except Exception as e:
        logger.error(f"Erro ao criar tabelas: {e}")