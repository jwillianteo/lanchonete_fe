from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from openpyxl import Workbook
from datetime import datetime
import os
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL', 'sqlite:///lanchonete.db')

# Corrigir a URL do banco de dados para usar 'postgresql://' e adicionar 'sslmode=require'
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if 'sslmode=require' not in database_url:
        database_url += '?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desabilitar rastreamento de modificações
db = SQLAlchemy(app)

# Modelo de Produto
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    valor_compra = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    itens_vendidos = db.relationship('ItemVenda', backref='produto', lazy=True, cascade="all, delete-orphan")

# Modelo de Venda
class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    data_venda = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('ItemVenda', backref='venda', lazy=True)

# Modelo de ItemVenda
class ItemVenda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey('venda.id'), nullable=False)

# Rota da Página Inicial
@app.route('/')
def home():
    return render_template('index.html')

# Rota de Vendas
@app.route('/vendas')
def vendas():
    try:
        produtos = Produto.query.all()
        return render_template('vendas.html', produtos=produtos)
    except Exception as e:
        logger.error(f"Erro ao carregar produtos: {e}")
        return jsonify({'success': False, 'message': 'Erro ao carregar produtos'}), 500

# Rota de Cadastrar Produto
@app.route('/cadastrar_produto', methods=['GET', 'POST'])
def cadastrar_produto():
    if request.method == 'POST':
        nome = request.form.get('nome')
        preco = request.form.get('preco')
        valor_compra = request.form.get('valor_compra')
        quantidade = request.form.get('quantidade')

        if not nome or not preco or not valor_compra or not quantidade:
            return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios!'}), 400

        try:
            preco = float(preco)
            valor_compra = float(valor_compra)
            quantidade = int(quantidade)
        except ValueError:
            return jsonify({'success': False, 'message': 'Valores inválidos para preço, valor de compra ou quantidade!'}), 400

        try:
            novo_produto = Produto(nome=nome, preco=preco, valor_compra=valor_compra, quantidade=quantidade)
            db.session.add(novo_produto)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Produto cadastrado com sucesso!', 'id': novo_produto.id})
        except Exception as e:
            logger.error(f"Erro ao cadastrar produto: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Erro ao cadastrar produto'}), 500
    return render_template('cadastrar_produto.html')

# Rota de Finalizar Venda
@app.route('/finalizar_venda', methods=['POST'])
def finalizar_venda():
    try:
        data = request.get_json()
        if not data or 'cliente' not in data or 'itens_vendidos' not in data:
            logger.error("Dados inválidos recebidos")
            return jsonify({'success': False, 'message': 'Dados inválidos!'}), 400

        cliente = data['cliente']
        itens_vendidos = data['itens_vendidos']

        if not cliente or not itens_vendidos:
            logger.error("Cliente ou itens não fornecidos")
            return jsonify({'success': False, 'message': 'Cliente e itens são obrigatórios!'}), 400

        nova_venda = Venda(cliente=cliente)
        db.session.add(nova_venda)
        db.session.commit()

        for item in itens_vendidos:
            if 'id' not in item or 'quantidade' not in item:
                logger.error("Dados do item inválidos")
                return jsonify({'success': False, 'message': 'Dados do item inválidos!'}), 400

            produto = Produto.query.get(item['id'])
            if not produto:
                logger.error(f"Produto com ID {item['id']} não encontrado")
                return jsonify({'success': False, 'message': f'Produto com ID {item["id"]} não encontrado!'}), 404

            if produto.quantidade < item['quantidade']:
                logger.error(f"Estoque insuficiente para o produto {produto.nome}")
                return jsonify({'success': False, 'message': f'Estoque insuficiente para o produto {produto.nome}!'}), 400

            produto.quantidade -= item['quantidade']
            item_venda = ItemVenda(produto_id=item['id'], quantidade=item['quantidade'], venda_id=nova_venda.id)
            db.session.add(item_venda)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Venda finalizada com sucesso!'})
    except Exception as e:
        logger.error(f"Erro ao finalizar venda: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno no servidor'}), 500

# Rota de Estoque
@app.route('/estoque')
def estoque():
    try:
        produtos = Produto.query.all()
        return render_template('estoque.html', produtos=produtos)
    except Exception as e:
        logger.error(f"Erro ao carregar estoque: {e}")
        return jsonify({'success': False, 'message': 'Erro ao carregar estoque'}), 500

# Rota para Atualizar Estoque
@app.route('/atualizar_estoque/<int:produto_id>', methods=['POST'])
def atualizar_estoque(produto_id):
    try:
        data = request.get_json()
        nova_quantidade = data.get('quantidade')

        if nova_quantidade is None:
            return jsonify({'success': False, 'message': 'Quantidade não fornecida!'}), 400

        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado!'}), 404

        produto.quantidade = nova_quantidade
        db.session.commit()
        return jsonify({'success': True, 'message': 'Estoque atualizado com sucesso!'})
    except Exception as e:
        logger.error(f"Erro ao atualizar estoque: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno no servidor'}), 500

# Rota para Excluir Produto
@app.route('/excluir_produto/<int:produto_id>', methods=['DELETE'])
def excluir_produto(produto_id):
    try:
        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado!'}), 404

        db.session.delete(produto)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Produto excluído com sucesso!'})
    except Exception as e:
        logger.error(f"Erro ao excluir produto: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Erro interno no servidor'}), 500

# Rota de Relatório de Vendas
@app.route('/relatorio_vendas')
def relatorio_vendas():
    try:
        vendas = Venda.query.all()
        relatorio = []

        for venda in vendas:
            for item in venda.itens:
                relatorio.append({
                    'venda_id': venda.id,
                    'cliente': venda.cliente,
                    'data_venda': venda.data_venda,
                    'produto': Produto.query.get(item.produto_id).nome,
                    'quantidade': item.quantidade,
                    'preco': Produto.query.get(item.produto_id).preco,
                    'total_item': item.quantidade * Produto.query.get(item.produto_id).preco
                })

        relatorio.sort(key=lambda x: x['total_item'], reverse=True)

        if not os.path.exists('static'):
            os.makedirs('static')

        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Vendas"
        ws.append(['Venda ID', 'Cliente', 'Data Venda', 'Produto', 'Quantidade', 'Preço', 'Total Item'])

        for item in relatorio:
            ws.append([item['venda_id'], item['cliente'], item['data_venda'], item['produto'], item['quantidade'], item['preco'], item['total_item']])

        file_path = 'static/relatorio_vendas.xlsx'
        wb.save(file_path)

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Erro ao gerar relatório de vendas: {e}")
        return jsonify({'success': False, 'message': 'Erro ao gerar relatório de vendas'}), 500

# Rota de Relatório de Estoque
@app.route('/relatorio_estoque')
def relatorio_estoque():
    try:
        produtos = Produto.query.all()
        relatorio = []

        for produto in produtos:
            relatorio.append({
                'produto': produto.nome,
                'quantidade_inicial': produto.quantidade + sum(item.quantidade for item in produto.itens_vendidos),
                'quantidade_atual': produto.quantidade
            })

        if not os.path.exists('static'):
            os.makedirs('static')

        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Estoque"
        ws.append(['Produto', 'Quantidade Inicial', 'Quantidade Atual'])

        for item in relatorio:
            ws.append([item['produto'], item['quantidade_inicial'], item['quantidade_atual']])

        file_path = 'static/relatorio_estoque.xlsx'
        wb.save(file_path)

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Erro ao gerar relatório de estoque: {e}")
        return jsonify({'success': False, 'message': 'Erro ao gerar relatório de estoque'}), 500

# Inicialização do Banco de Dados e Execução do App
if __name__ == '__main__':
    with app.app_context():
        logger.info("Criando tabelas...")
        db.create_all()
        logger.info("Tabelas criadas com sucesso!")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)