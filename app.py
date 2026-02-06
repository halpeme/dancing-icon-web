"""
Dancing Sticker Stage - Flask Server
Phone users take photos -> AI removes background -> stickers dance on stage
"""

import io
import json
import uuid
import socket
import base64
import random
import queue
from flask import Flask, render_template, request, Response, jsonify
from PIL import Image
from rembg import remove, new_session
import qrcode

app = Flask(__name__)

# In-memory state
stickers = []  # List of {id, image_base64, x, y}
MAX_STICKERS = 20
sse_clients = []  # Active SSE client queues

# Background removal sessions - let users choose speed vs quality
bg_sessions = {
    'fast': new_session('u2net'),           # Default U2Net - fast (~0.3s)
    'quality': new_session('birefnet-general')  # BiRefNet - slow (~0.8s) but better
}


def get_local_ip():
    """Detect local network IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_qr_base64(url):
    """Generate QR code as base64 PNG"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def broadcast(event_data):
    """Send event to all connected SSE clients"""
    message = f"data: {json.dumps(event_data)}\n\n"
    dead_clients = []

    for client_queue in sse_clients:
        try:
            client_queue.put_nowait(message)
        except queue.Full:
            dead_clients.append(client_queue)

    for dead in dead_clients:
        sse_clients.remove(dead)


def add_sticker(image_base64):
    """Add sticker to list, remove oldest if full"""
    sticker = {
        'id': str(uuid.uuid4()),
        'image': image_base64,
        'x': random.randint(10, 90),
        'y': random.randint(10, 90)
    }

    removed_id = None
    if len(stickers) >= MAX_STICKERS:
        removed = stickers.pop(0)
        removed_id = removed['id']
        broadcast({'type': 'remove', 'id': removed_id})

    stickers.append(sticker)
    broadcast({'type': 'add', 'sticker': sticker})

    return sticker


# Routes

@app.route('/')
def stage():
    """Stage page - displays QR and dancing stickers"""
    local_ip = get_local_ip()
    camera_url = f"http://{local_ip}:5000/camera"
    qr_base64 = generate_qr_base64(camera_url)

    # Detect overlay mode from URL parameter
    overlay_mode = request.args.get('mode') == 'overlay'

    return render_template('stage.html', qr_base64=qr_base64, camera_url=camera_url, overlay_mode=overlay_mode)


@app.route('/camera')
def camera():
    """Camera page - mobile photo capture"""
    return render_template('camera.html')


@app.route('/process', methods=['POST'])
def process():
    """Process photo: remove background and return result for preview"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo provided'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Get model preference (default to fast)
    model = request.form.get('model', 'fast')
    session = bg_sessions.get(model, bg_sessions['fast'])

    try:
        # Load and resize image
        img = Image.open(file.stream)

        # Fix rotation from EXIF data (phone photos)
        try:
            from PIL import ExifTags
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = img._getexif()
            if exif is not None:
                orientation_value = exif.get(orientation)
                if orientation_value == 3:
                    img = img.rotate(180, expand=True)
                elif orientation_value == 6:
                    img = img.rotate(270, expand=True)
                elif orientation_value == 8:
                    img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            pass

        img.thumbnail((800, 800), Image.Resampling.LANCZOS)

        # Convert to bytes for rembg
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Remove background with selected model
        output = remove(img_bytes.read(), session=session)

        # Convert to base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(output).decode()}"

        return jsonify({'success': True, 'image': image_base64})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/submit', methods=['POST'])
def submit():
    """Submit processed sticker to stage"""
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': 'No image provided'}), 400

    try:
        image_base64 = data['image']
        rotation = data.get('rotation', 0)

        # Apply rotation if needed
        if rotation != 0:
            # Decode base64, rotate, re-encode
            img_data = base64.b64decode(image_base64.split(',')[1])
            img = Image.open(io.BytesIO(img_data))
            img = img.rotate(-rotation, expand=True)  # Negative because CSS rotation is clockwise

            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            image_base64 = f"data:image/png;base64,{base64.b64encode(img_bytes.getvalue()).decode()}"

        sticker = add_sticker(image_base64)
        return jsonify({'success': True, 'sticker_id': sticker['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload():
    """Legacy: Handle photo upload, remove background, add to stage"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo provided'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Load and resize image
        img = Image.open(file.stream)
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)

        # Convert to bytes for rembg
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Remove background (legacy route uses fast model)
        output = remove(img_bytes.read(), session=bg_sessions['fast'])

        # Convert to base64
        image_base64 = f"data:image/png;base64,{base64.b64encode(output).decode()}"

        # Add to stage
        sticker = add_sticker(image_base64)

        return jsonify({'success': True, 'sticker_id': sticker['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stream')
def stream():
    """SSE endpoint for real-time updates"""
    def event_stream():
        client_queue = queue.Queue(maxsize=100)
        sse_clients.append(client_queue)

        try:
            # Send current stickers on connect
            yield f"data: {json.dumps({'type': 'init', 'stickers': stickers})}\n\n"

            # Wait for new events
            while True:
                message = client_queue.get()
                yield message
        except GeneratorExit:
            pass
        finally:
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )


if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 5000

    print(f"\n{'='*50}")
    print(f"  Dancing Sticker Stage")
    print(f"{'='*50}")
    print(f"  Stage:  http://{local_ip}:{port}/")
    print(f"  Camera: http://{local_ip}:{port}/camera")
    print(f"\n  Scan QR code on stage to connect phones")
    print(f"{'='*50}\n")

    app.run(host='0.0.0.0', port=port, threaded=True, debug=True)
