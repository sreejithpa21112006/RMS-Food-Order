from flask import Blueprint, render_template, request, url_for, send_file
import qrcode
import io
from database import get_db

public_bp = Blueprint('public', __name__)

@public_bp.route("/")
def home():
    return render_template("home.html")

@public_bp.route("/menu")
def public_menu():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT f.item_name, f.price, f.is_available, c.category_name
        FROM food_items f
        LEFT JOIN categories c ON f.category_id = c.category_id
        WHERE f.is_available = TRUE
        ORDER BY c.category_name, f.item_name
    """)
    items = cursor.fetchall()
    
    menu_data = {}
    for item in items:
        cat = item['category_name'] or 'Other'
        if cat not in menu_data:
            menu_data[cat] = []
        menu_data[cat].append(item)
        
    cursor.close()
    db.close()
    return render_template("menu.html", menu_data=menu_data)

@public_bp.route("/generate-qr")
def generate_qr():
    menu_url = request.host_url.rstrip('/') + url_for('public.public_menu')
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(menu_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png', as_attachment=False, download_name='menu_qr.png')
