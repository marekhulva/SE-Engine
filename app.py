from flask import Flask, request, jsonify, send_file, render_template
import json, os, tempfile
from layout_engine import generate_layout
from renderer_pptx import render_pptx

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/layout', methods=['POST'])
def layout():
    scenario = request.get_json()
    data = generate_layout(scenario)
    return jsonify(data)

@app.route('/scenario')
def scenario():
    with open(os.path.join(BASE_DIR, 'scenario_current.json')) as f:
        return f.read(), 200, {'Content-Type': 'application/json'}

@app.route('/download', methods=['POST'])
def download():
    scenario = request.get_json()
    layout_data = generate_layout(scenario)
    tmp = tempfile.NamedTemporaryFile(suffix='.pptx', delete=False)
    tmp.close()
    render_pptx(layout_data, tmp.name)
    return send_file(tmp.name, as_attachment=True, download_name='diagram.pptx',
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_file(os.path.join(BASE_DIR, 'assets', filename))

@app.route('/output/<path:filename>')
def output(filename):
    return send_file(os.path.join(BASE_DIR, 'output', filename),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

if __name__ == '__main__':
    app.run(debug=True, port=5050, host='0.0.0.0')
