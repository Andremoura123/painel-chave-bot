# server.py
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, g
import sqlite3
import uuid
from datetime import datetime

app = Flask(__name__)
DATABASE = 'keys.db'

# --- Gerenciamento da Conexão com o Banco de Dados (Padrão Flask) ---

def get_db():
    """
    Abre uma nova conexão com o banco de dados se não houver uma no contexto da requisição atual.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        # PONTO CRÍTICO: Permite que os resultados do DB sejam acessados como dicionários.
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """
    Fecha a conexão com o banco de dados automaticamente ao final da requisição.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Inicializa o banco de dados e cria a tabela se ela não existir."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                client_name TEXT,
                discord_server_id TEXT,
                creation_date TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        ''')
        db.commit()

# Substitua a sua função validate_key por esta
@app.route('/validate_key', methods=['POST'])
def validate_key():
    print("\n--- Endpoint /validate_key foi chamado! ---") # LOG 1
    
    data = request.json
    key = data.get('key')
    server_id = data.get('server_id')

    print(f"Dados recebidos do bot: key='{key}', server_id='{server_id}'") # LOG 2

    if not key or not server_id:
        print("ERRO: Chave ou ID do servidor ausente no request.")
        return jsonify({'status': 'error', 'message': 'Chave ou ID do servidor ausente.'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT discord_server_id, is_active FROM license_keys WHERE key = ?", (key,))
    result = cursor.fetchone()

    if not result:
        print(f"ERRO: A chave '{key}' não foi encontrada no banco de dados.")
        return jsonify({'status': 'error', 'message': 'Chave inválida.'}), 403

    db_server_id = result['discord_server_id']
    is_active = result['is_active']
    print(f"Dados do DB para a chave '{key}': db_server_id='{db_server_id}', is_active={is_active}") # LOG 3

    if not is_active:
        print(f"ERRO: A chave '{key}' está inativa.")
        return jsonify({'status': 'error', 'message': 'Esta chave foi desativada.'}), 403

    if db_server_id is None:
        print(f"A chave '{key}' é nova. Tentando vincular ao server_id '{server_id}'...") # LOG 4
        cursor.execute("UPDATE license_keys SET discord_server_id = ? WHERE key = ?", (server_id, key))
        db.commit()
        print("SUCESSO: Banco de dados atualizado!")
        return jsonify({'status': 'success', 'message': 'Chave validada e vinculada a este servidor.'})

    if db_server_id == server_id:
        print(f"A chave '{key}' já está vinculada a este servidor. Re-validando...")
        return jsonify({'status': 'success', 'message': 'Chave re-validada para este servidor.'})
    else:
        print(f"ERRO: A chave '{key}' já está em uso no servidor '{db_server_id}'.")
        return jsonify({'status': 'error', 'message': 'Esta chave já está em uso em outro servidor.'}), 403

# --- Painel de Gerenciamento Web (CORRIGIDO) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        if 'generate_key' in request.form:
            client_name = request.form.get('client_name', 'Sem Nome')
            new_key = str(uuid.uuid4())
            creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO license_keys (key, client_name, creation_date) VALUES (?, ?, ?)",
                (new_key, client_name, creation_date)
            )
        elif 'toggle_key' in request.form:
            key_id = request.form.get('key_id')
            cursor.execute("SELECT is_active FROM license_keys WHERE id = ?", (key_id,))
            current_status = cursor.fetchone()['is_active']
            new_status = 0 if current_status == 1 else 1
            cursor.execute("UPDATE license_keys SET is_active = ? WHERE id = ?", (new_status, key_id))
        elif 'delete_key' in request.form:
            key_id = request.form.get('key_id')
            cursor.execute("DELETE FROM license_keys WHERE id = ? AND is_active = 0", (key_id,))
        
        db.commit()
        return redirect(url_for('admin_panel'))
    
    cursor.execute("SELECT id, key, client_name, discord_server_id, creation_date, is_active FROM license_keys ORDER BY id DESC")
    keys = cursor.fetchall()

    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Painel de Chaves</title>
            <style>
                body { font-family: sans-serif; margin: 2em; background: #2c2f33; color: #fff; }
                h1, h2 { color: #7289da; }
                table { width: 100%; border-collapse: collapse; margin-top: 1em;}
                th, td { padding: 8px; border: 1px solid #444; text-align: left; }
                th { background-color: #7289da; }
                button, input { background-color: #7289da; color: white; padding: 10px; border: none; cursor: pointer; border-radius: 3px; margin-right: 5px; }
                input[type=text] { background-color: #40444b; border: 1px solid #222; }
                form { margin-bottom: 1.5em; }
                .active { color: lightgreen; }
                .inactive { color: red; }
                .delete-btn { background-color: #f04747; }
                .action-forms { display: flex; align-items: center; }
            </style>
        </head>
        <body>
            <h1>Painel de Gerenciamento de Chaves</h1>
            <form method="post">
                <label for="client_name">Nome do Cliente:</label>
                <input type="text" id="client_name" name="client_name" required>
                <button name="generate_key" type="submit">Gerar Nova Chave</button>
            </form>
            <h2>Chaves Vendidas</h2>
            <table>
                <tr>
                    <th>ID</th><th>Nome do Cliente</th><th>Chave</th><th>ID do Servidor</th><th>Data</th><th>Status</th><th>Ações</th>
                </tr>
                {% for k in keys %}
                <tr>
                    <td>{{ k['id'] }}</td><td>{{ k['client_name'] }}</td><td>{{ k['key'] }}</td><td>{{ k['discord_server_id'] or 'Ainda não usado' }}</td><td>{{ k['creation_date'] }}</td>
                    <td class="{{ 'active' if k['is_active'] else 'inactive' }}">{{ 'Ativa' if k['is_active'] else 'Inativa' }}</td>
                    <td>
                        <div class="action-forms">
                            <form method="post" style="margin:0;">
                                <input type="hidden" name="key_id" value="{{ k['id'] }}">
                                <button name="toggle_key" type="submit">{{ 'Desativar' if k['is_active'] else 'Reativar' }}</button>
                            </form>
                            {% if not k['is_active'] %}
                            <form method="post" style="margin:0;" onsubmit="return confirm('Você tem certeza que quer deletar esta chave permanentemente?');">
                                <input type="hidden" name="key_id" value="{{ k['id'] }}">
                                <button name="delete_key" type="submit" class="delete-btn">Deletar</button>
                            </form>
                            {% endif %}
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
    ''', keys=keys)

if __name__ == '__main__':
    init_db()
    # Para produção, considere usar um servidor WSGI como Gunicorn.
    # Ex: gunicorn --bind 0.0.0.0:5000 server:app
    app.run(debug=False, host='0.0.0.0', port=5000)