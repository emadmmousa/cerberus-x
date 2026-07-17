from flask import Flask, jsonify, render_template
from .celery_app import app as celery_app
from celery.result import AsyncResult

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status/<task_id>')
def task_status(task_id):
    result = AsyncResult(task_id, app=celery_app)
    response = {
        'task_id': task_id,
        'state': result.state,
        'info': result.info,
    }
    if result.state == 'SUCCESS':
        # For chain results, we might want the full list – we can store it in backend
        response['result'] = result.result
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)