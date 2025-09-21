from flask import Flask, request, jsonify, render_template_string
import sqlite3
import uuid
from datetime import datetime

app = Flask(__name__)

# --- Configuração do Banco de Dados ---
def init_db():
    conn = sqlite3.connect('keys.db')
    cursor = conn.cursor()
    # Tabela atualizada com a coluna 'client_name'
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
    conn.commit()
    conn.close()

# --- Endpoint da API para o Bot Validar a Chave (NÃO PRECISA DE MUDANÇAS) ---
@app.route('/validate_key', methods=['POST'])
def validate_key():
    data = request.json
    key = data.get('key')
    server_id = data.get('server_id')

    if not key or not server_id:
        return jsonify({'status': 'error', 'message': 'Chave ou ID do servidor ausente.'}), 400

    conn = sqlite3.connect('keys.db')
    cursor = conn.cursor()
    cursor.execute("SELECT discord_server_id, is_active FROM license_keys WHERE key = ?", (key,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Chave inválida.'}), 403

    db_server_id, is_active = result

    if not is_active:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Esta chave foi desativada.'}), 403

    if db_server_id is None:
        cursor.execute("UPDATE license_keys SET discord_server_id = ? WHERE key = ?", (server_id, key))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Chave validada e vinculada a este servidor.'})

    if db_server_id == server_id:
        conn.close()
        return jsonify({'status': 'success', 'message': 'Chave re-validada para este servidor.'})
    else:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Esta chave já está em uso em outro servidor.'}), 403

# --- Painel de Gerenciamento Web (Atualizado) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    conn = sqlite3.connect('keys.db')
    cursor = conn.cursor()

    # Ação para gerar uma nova chave
    if request.method == 'POST' and 'generate_key' in request.form:
        client_name = request.form.get('client_name', 'Sem Nome') # Pega o nome do formulário
        new_key = str(uuid.uuid4())
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO license_keys (key, client_name, creation_date) VALUES (?, ?, ?)",
            (new_key, client_name, creation_date)
        )
        conn.commit()

    # Ação para desativar/reativar uma chave
    if request.method == 'POST' and 'toggle_key' in request.form:
        key_id = request.form.get('key_id')
        cursor.execute("SELECT is_active FROM license_keys WHERE id = ?", (key_id,))
        current_status = cursor.fetchone()[0]
        new_status = 0 if current_status == 1 else 1
        cursor.execute("UPDATE license_keys SET is_active = ? WHERE id = ?", (new_status, key_id))
        conn.commit()
    
    cursor.execute("SELECT id, key, client_name, discord_server_id, creation_date, is_active FROM license_keys ORDER BY id DESC")
    keys = cursor.fetchall()
    conn.close()

    # HTML atualizado com o campo de nome
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
                button, input { background-color: #7289da; color: white; padding: 10px; border: none; cursor: pointer; border-radius: 3px; }
                input[type=text] { background-color: #40444b; border: 1px solid #222; }
                form { margin-bottom: 1.5em; }
                .active { color: lightgreen; }
                .inactive { color: red; }
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
                    <th>ID</th><th>Nome do Cliente</th><th>Chave</th><th>ID do Servidor</th><th>Data</th><th>Status</th><th>Ação</th>
                </tr>
                {% for k in keys %}
                <tr>
                    <td>{{ k[0] }}</td><td>{{ k[2] }}</td><td>{{ k[1] }}</td><td>{{ k[3] or 'Ainda não usado' }}</td><td>{{ k[4] }}</td>
                    <td class="{{ 'active' if k[5] else 'inactive' }}">{{ 'Ativa' if k[5] else 'Inativa' }}</td>
                    <td>
                        <form method="post" style="margin:0;">
                            <input type="hidden" name="key_id" value="{{ k[0] }}">
                            <button name="toggle_key" type="submit">{{ 'Desativar' if k[5] else 'Reativar' }}</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
    ''', keys=keys)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)