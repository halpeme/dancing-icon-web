"""
Dancing Sticker Stage - Flask Server
Phone users take photos -> AI removes background -> stickers dance on stage

Performance Optimizations:
- Lazy-load rembg models (birefnet, sam) on first use
- EXIF auto-rotation using ImageOps.exif_transpose()
- URL-based image storage (not base64)

GPU Acceleration (optional):
Install onnxruntime-gpu for 5-10x background removal speedup:
  pip install onnxruntime-gpu (NVIDIA CUDA)
  pip install onnxruntime-directml (Windows DirectML)
"""

import io
import os
import json
import uuid
import socket
import base64
import random
import queue
import numpy as np
from datetime import datetime
from flask import Flask, render_template, request, Response, jsonify, send_from_directory, session
from PIL import Image
from rembg import remove, new_session
import qrcode

app = Flask(__name__)
app.secret_key = 'dancing-sticker-secure-key-2026'  # For session management

# Create uploads directory for saving processed stickers
UPLOADS_DIR = 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

# In-memory state
stickers = []  # List of {id, image (URL), x, y}
MAX_STICKERS = 20
sse_clients = []  # Active SSE client queues

# Background removal sessions - lazy-loaded for faster startup
# Only preload 'fast' model, others loaded on first use
bg_sessions = {
    'fast': new_session('u2net'),  # Preload fast model (~176MB)
}

def get_bg_session(model_name):
    """Lazy-load background removal sessions

    Models:
    - u2net: Fast, good quality (~0.3s)
    - birefnet-general: Slower, best quality (~0.8s)
    - sam: Manual point-based selection

    GPU Acceleration:
    Install onnxruntime-gpu for 5-10x speedup:
    pip install onnxruntime-gpu (CUDA) or onnxruntime-directml (Windows)
    """
    if model_name not in bg_sessions:
        print(f"[INFO] Loading '{model_name}' model (first use)...")
        bg_sessions[model_name] = new_session(model_name)
        print(f"[INFO] Model '{model_name}' loaded successfully")

    return bg_sessions[model_name]


def png_to_webp(png_bytes, quality=90):
    """Convert PNG bytes to WebP for 50-70% size reduction

    Args:
        png_bytes: PNG image as bytes
        quality: WebP quality (1-100, default 90)

    Returns:
        WebP image as bytes
    """
    img = Image.open(io.BytesIO(png_bytes))
    webp_bytes = io.BytesIO()
    img.save(webp_bytes, format='WEBP', quality=quality, method=6)  # method=6 = slowest but best compression
    return webp_bytes.getvalue()


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


def add_sticker(image_url):
    """Add sticker to list, remove oldest if full

    Args:
        image_url: File URL like '/uploads/20260208_143022_456.png'
    """
    sticker = {
        'id': str(uuid.uuid4()),
        'image': image_url,
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

    # Get mode (auto or manual)
    mode = request.form.get('mode', 'auto')

    # Get model preference for auto mode (default to fast)
    model = request.form.get('model', 'fast')

    # Select session based on mode (lazy-loaded)
    if mode == 'manual':
        session = get_bg_session('sam')
    else:
        session = get_bg_session(model if model in ['u2net', 'birefnet-general', 'sam'] else 'u2net')

    try:
        # Load and resize image
        img = Image.open(file.stream)

        # Fix rotation from EXIF data (phone photos)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img) or img
        except Exception:
            pass

        img.thumbnail((800, 800), Image.Resampling.LANCZOS)

        # Convert to bytes for rembg
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Remove background
        if mode == 'manual':
            # Get points and labels from request
            points_json = request.form.get('points', '[]')
            labels_json = request.form.get('labels', '[]')

            points = json.loads(points_json)
            labels = json.loads(labels_json)

            # Convert to numpy arrays
            input_points = np.array(points, dtype=np.float32)
            input_labels = np.array(labels, dtype=np.int32)

            # Remove background with manual guidance
            output = remove(
                img_bytes.read(),
                session=session,
                input_points=input_points,
                input_labels=input_labels,
                post_process_mask=True  # Smooth edges
            )
        else:
            # Auto mode - use selected model
            output = remove(img_bytes.read(), session=session)

        # Convert PNG to WebP for 50-70% size reduction
        webp_output = png_to_webp(output, quality=90)

        # Convert to base64
        image_base64 = f"data:image/webp;base64,{base64.b64encode(webp_output).decode()}"

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
            # Decode base64, rotate, re-encode as WebP
            raw_data = base64.b64decode(image_base64.split(',')[1])
            img = Image.open(io.BytesIO(raw_data))
            img = img.rotate(-rotation, expand=True)  # Negative because CSS rotation is clockwise

            img_bytes = io.BytesIO()
            img.save(img_bytes, format='WEBP', quality=90, method=6)
            save_bytes = img_bytes.getvalue()
        else:
            save_bytes = base64.b64decode(image_base64.split(',')[1])

        # CRITICAL: Save file FIRST before adding to stickers list
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename = f"{timestamp}.webp"
            filepath = os.path.join(UPLOADS_DIR, filename)

            with open(filepath, 'wb') as f:
                f.write(save_bytes)

            print(f"[INFO] Saved sticker: {filename}")
        except Exception as e:
            # FAIL REQUEST - file save is required for URL-based system
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

        # Create file URL
        image_url = f"/uploads/{filename}"

        # Add sticker with URL instead of base64
        sticker = add_sticker(image_url)
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
        output = remove(img_bytes.read(), session=get_bg_session('u2net'))

        # Convert to WebP for smaller file size
        webp_output = png_to_webp(output, quality=90)

        # Save file to disk
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            filename = f"{timestamp}.webp"
            filepath = os.path.join(UPLOADS_DIR, filename)

            with open(filepath, 'wb') as f:
                f.write(webp_output)

            print(f"[INFO] Saved sticker: {filename}")
        except Exception as e:
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

        # Create file URL
        image_url = f"/uploads/{filename}"

        # Add to stage with URL
        sticker = add_sticker(image_url)

        return jsonify({'success': True, 'sticker_id': sticker['id']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/active_stickers')
def get_active_stickers():
    """Get list of currently active sticker filenames"""
    # Extract filenames from active stickers' image URLs
    active_filenames = []
    for sticker in stickers:
        # image URL format: '/uploads/20260208_143022_456.webp'
        filename = sticker['image'].split('/')[-1]
        active_filenames.append(filename)

    return jsonify({'active': active_filenames})


@app.route('/api/toggle_sticker', methods=['POST'])
def toggle_sticker():
    """Activate or deactivate a sticker from the gallery

    Request JSON:
        filename: str - The sticker filename (e.g., '20260208_143022_456.webp')
        action: str - 'activate' or 'deactivate'
    """
    data = request.get_json()
    if not data or 'filename' not in data or 'action' not in data:
        return jsonify({'error': 'Missing filename or action'}), 400

    filename = data['filename']
    action = data['action']
    image_url = f"/uploads/{filename}"

    # Verify file exists
    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404

    if action == 'activate':
        # Check if already active
        for sticker in stickers:
            if sticker['image'] == image_url:
                return jsonify({'error': 'Already active'}), 400

        # Add to stage with entrance animation (same as new submission)
        sticker = add_sticker(image_url)
        return jsonify({'success': True, 'sticker_id': sticker['id'], 'action': 'activated'})

    elif action == 'deactivate':
        # Find and remove from active stickers
        for i, sticker in enumerate(stickers):
            if sticker['image'] == image_url:
                removed = stickers.pop(i)
                broadcast({'type': 'remove', 'id': removed['id']})
                return jsonify({'success': True, 'sticker_id': removed['id'], 'action': 'deactivated'})

        return jsonify({'error': 'Not currently active'}), 400

    else:
        return jsonify({'error': 'Invalid action. Use "activate" or "deactivate"'}), 400


@app.route('/api/auth', methods=['POST'])
def authenticate():
    """Verify PIN code for gallery delete access

    Request JSON:
        pin: str - The PIN code (should be '1234')
    """
    data = request.get_json()
    if not data or 'pin' not in data:
        return jsonify({'error': 'Missing PIN'}), 400

    pin = str(data['pin'])
    if pin == '1234':
        session['authenticated'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Invalid PIN'}), 401


@app.route('/api/check_auth')
def check_auth():
    """Check if current session is authenticated"""
    return jsonify({'authenticated': session.get('authenticated', False)})


@app.route('/api/delete_stickers', methods=['POST'])
def delete_stickers():
    """Delete stickers from gallery (requires authentication)

    Request JSON:
        filenames: list[str] - List of filenames to delete
    """
    # Check authentication
    if not session.get('authenticated', False):
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    if not data or 'filenames' not in data:
        return jsonify({'error': 'Missing filenames'}), 400

    filenames = data['filenames']
    if not isinstance(filenames, list) or len(filenames) == 0:
        return jsonify({'error': 'Invalid filenames list'}), 400

    deleted = []
    errors = []

    for filename in filenames:
        # Security: ensure filename doesn't contain path traversal
        if '/' in filename or '\\' in filename or '..' in filename:
            errors.append({'filename': filename, 'error': 'Invalid filename'})
            continue

        filepath = os.path.join(UPLOADS_DIR, filename)

        # Check if file exists
        if not os.path.exists(filepath):
            errors.append({'filename': filename, 'error': 'File not found'})
            continue

        try:
            # Remove from active stickers if present
            image_url = f"/uploads/{filename}"
            for i, sticker in enumerate(stickers):
                if sticker['image'] == image_url:
                    removed = stickers.pop(i)
                    broadcast({'type': 'remove', 'id': removed['id']})
                    break

            # Delete file from filesystem
            os.remove(filepath)
            deleted.append(filename)
            print(f"[INFO] Deleted sticker: {filename}")

        except Exception as e:
            errors.append({'filename': filename, 'error': str(e)})

    return jsonify({
        'success': True,
        'deleted': deleted,
        'errors': errors,
        'deleted_count': len(deleted),
        'error_count': len(errors)
    })


@app.route('/gallery')
def gallery():
    """Gallery page - view all saved stickers"""
    # List all image files in uploads directory
    images = []
    if os.path.exists(UPLOADS_DIR):
        images = [f for f in os.listdir(UPLOADS_DIR) if f.endswith(('.png', '.webp'))]
        # Sort by filename descending (newest first - timestamps in filename)
        images.sort(reverse=True)

    return render_template('gallery.html', images=images)


@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded images with caching headers"""
    response = send_from_directory(UPLOADS_DIR, filename)
    # Cache for 1 day (files are immutable due to timestamp naming)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


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
