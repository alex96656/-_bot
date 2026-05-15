from flask import Flask, render_template_string
import os
import datetime

app = Flask(__name__)

# Simple HTML template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Admin Panel</title>
    <style>
        body { font-family: sans-serif; text-align: center; background: #f4f4f4; }
        .container { margin-top: 50px; background: white; padding: 20px; display: inline-block; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .status-online { color: green; font-weight: bold; }
        .status-offline { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Monitoring Panel</h1>
        <p>Current Server Time: {{ time }}</p>
        <hr>
        <h3>Bot Status: 
            {% if online %}
                <span class="status-online">● ONLINE</span>
            {% else %}
                <span class="status-offline">● OFFLINE</span>
            {% endif %}
        </h3>
    </div>
</body>
</html>
"""

def is_bot_running():
    # This checks if your bot script is currently running in the background
    # Replace 'whatsapp_telegram_bot_Version2.py' with your exact filename
    output = os.popen('pgrep -f whatsapp_telegram_bot_Version2.py').read()
    return len(output) > 0

@app.route('/')
def dashboard():
    status = is_bot_running()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, online=status, time=now)

if __name__ == '__main__':
    # Default port for Flask is 5000
    app.run(host='0.0.0.0', port=5000)
