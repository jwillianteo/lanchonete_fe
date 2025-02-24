from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from openpyxl import Workbook
from datetime import datetime
import os  # Importar o módulo os para acessar variáveis de ambiente

app = Flask(__name__)

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL', 'sqlite:///lanchonete.db')

# Remover prefixo "DATABASE_URL=" se estiver presente
if database_url.startswith('DATABASE_URL='):
    database_url = database_url[len('DATABASE_URL='):]

# Adicionar suporte a SSL para PostgreSQL (se necessário)
if "postgresql" in database_url and "sslmode" not in database_url:
    database_url += "?sslmode=require"

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
    produtos = Produto.query.all()
    return render_template('vendas.html', produtos=produtos)

# Rota de Cadastrar Produto
@app.route('/cadastrar_produto', methods=['GET', 'POST'])
def cadastrar_produto():
    if request.method == 'POST':
        nome = request.form.get('nome')
        preco = request.form.get('preco')
        valor_compra = request.form.get('valor_compra')
        quantidade = request.form.get('quantidade')

        # Validação dos campos
        if not nome or not preco or not valor_compra or not quantidade:
            return "Todos os campos são obrigatórios!", 400

        try:
            preco = float(preco)
            valor_compra = float(valor_compra)
            quantidade = int(quantidade)

            # Validação de valores positivos
            if preco <= 0 or valor_compra <= 0 or quantidade < 0:
                return "Valores inválidos para preço, valor de compra ou quantidade!", 400

        except ValueError:
            return "Valores inválidos para preço, valor de compra ou quantidade!", 400

        # Criação do novo produto
        novo_produto = Produto(nome=nome, preco=preco, valor_compra=valor_compra, quantidade=quantidade)

        try:
            db.session.add(novo_produto)
            db.session.commit()
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            return f"Erro ao cadastrar produto: {str(e)}", 500

    return render_template('cadastrar_produto.html')

# Rota de Finalizar Venda
@app.route('/finalizar_venda', methods=['POST'])
def finalizar_venda():
    data = request.get_json()
    if not data or 'cliente' not in data or 'itens_vendidos' not in data:
        return jsonify({'success': False, 'message': 'Dados inválidos!'}), 400

    cliente = data['cliente']
    itens_vendidos = data['itens_vendidos']

    if not cliente or not itens_vendidos:
        return jsonify({'success': False, 'message': 'Cliente e itens são obrigatórios!'}), 400

    try:
        nova_venda = Venda(cliente=cliente)
        db.session.add(nova_venda)
        db.session.commit()

        for item in itens_vendidos:
            if 'id' not in item or 'quantidade' not in item:
                return jsonify({'success': False, 'message': 'Dados do item inválidos!'}), 400

            produto = Produto.query.get(item['id'])
            if not produto:
                return jsonify({'success': False, 'message': f'Produto com ID {item["id"]} não encontrado!'}), 404

            if produto.quantidade < item['quantidade']:
                return jsonify({'success': False, 'message': f'Estoque insuficiente para o produto {produto.nome}!'}), 400

            produto.quantidade -= item['quantidade']
            item_venda = ItemVenda(produto_id=item['id'], quantidade=item['quantidade'], venda_id=nova_venda.id)
            db.session.add(item_venda)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Rota de Estoque
@app.route('/estoque')
def estoque():
    produtos = Produto.query.all()
    return render_template('estoque.html', produtos=produtos)

# Rota para Atualizar Estoque
@app.route('/atualizar_estoque/<int:produto_id>', methods=['POST'])
def atualizar_estoque(produto_id):
    data = request.get_json()
    nova_quantidade = data.get('quantidade')

    if nova_quantidade is None:
        return jsonify({'success': False, 'message': 'Quantidade não fornecida!'}), 400

    try:
        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado!'}), 404

        produto.quantidade = nova_quantidade
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Rota para Excluir Produto
@app.route('/excluir_produto/<int:produto_id>', methods=['DELETE'])
def excluir_produto(produto_id):
    try:
        produto = Produto.query.get(produto_id)
        if not produto:
            return jsonify({'success': False, 'message': 'Produto não encontrado!'}), 404

        db.session.delete(produto)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

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

        # Verificar se o diretório 'static' existe, se não, criar
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
        return f"Erro ao gerar relatório de vendas: {str(e)}", 500

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

        # Verificar se o diretório 'static' existe, se não, criar
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
        return f"Erro ao gerar relatório de estoque: {str(e)}", 500

# Inicialização do Banco de Dados e Execução do App
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)