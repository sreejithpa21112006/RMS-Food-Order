from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import date
from flask_mail import Message
from database import get_db
from extensions import mail, socketio
from routes.auth import admin_required

orders_bp = Blueprint('orders', __name__)

@orders_bp.route("/orders/new", methods=["GET", "POST"])
def new_order():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM food_items WHERE is_available = TRUE ORDER BY item_name")
    food_list = cursor.fetchall()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        customer_mobile = request.form.get("customer_mobile", "").strip()
        customer_email = request.form.get("customer_email", "").strip()

        if not customer_name or not customer_mobile:
            flash("Customer name and mobile number are required.", "error")
            cursor.close()
            db.close()
            return redirect(url_for("orders.new_order"))

        selected_items = []
        total_amount = 0.0
        for item in food_list:
            qty_str = request.form.get(f"qty_{item['item_id']}", "0").strip()
            try:
                qty = int(qty_str) if qty_str else 0
            except ValueError:
                qty = 0
            if qty > 0:
                line_total = float(item["price"]) * qty
                total_amount += line_total
                selected_items.append((item["item_id"], item["item_name"], item["price"], qty))

        if not selected_items:
            flash("Please select at least one food item with a quantity greater than 0.", "error")
            cursor.close()
            db.close()
            return redirect(url_for("orders.new_order"))

        order_date = date.today()

        cursor.execute(
            """INSERT INTO orders (customer_name, customer_mobile, customer_email, order_date, status, total_amount)
               VALUES (%s, %s, %s, %s, 'new', %s)""",
            (customer_name, customer_mobile, customer_email if customer_email else None, order_date, total_amount)
        )
        order_id = cursor.lastrowid

        for item_id, item_name, price, qty in selected_items:
            cursor.execute(
                """INSERT INTO order_items (order_id, item_id, item_name, price, quantity)
                   VALUES (%s, %s, %s, %s, %s)""",
                (order_id, item_id, item_name, price, qty)
            )

        db.commit()
        cursor.close()
        db.close()
        
        if customer_email:
            try:
                msg = Message("Order Confirmation", recipients=[customer_email])
                msg.body = f"Hello {customer_name},\n\nYour order has been placed successfully!\nTotal amount: ₹{total_amount:.2f}\n\nThank you for ordering with us."
                mail.send(msg)
            except Exception as e:
                print("Failed to send email:", e)
                flash("Order created but failed to send email. Check SMTP settings.", "warning")

        flash(f"Order #{order_id} created successfully for {customer_name}.", "success")
        try:
            socketio.emit('kitchen_update', {'action': 'refresh'})
        except Exception as e:
            print("SocketIO Error:", e)
        if session.get('role') == 'admin':
            return redirect(url_for("orders.list_orders"))
        return redirect(url_for("public.home"))

    cursor.close()
    db.close()
    return render_template("new_order.html", food_list=food_list)

@orders_bp.route("/orders")
@admin_required
def list_orders():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    cursor.execute("SELECT COUNT(*) as total FROM orders")
    total_orders = cursor.fetchone()['total']
    total_pages = (total_orders + per_page - 1) // per_page
    if total_pages == 0:
        total_pages = 1
        
    cursor.execute(
        """SELECT order_id, customer_mobile, customer_name, order_date, total_amount, status
           FROM orders ORDER BY order_date DESC, order_id DESC LIMIT %s OFFSET %s""",
        (per_page, offset)
    )
    orders = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("list_orders.html", orders=orders, page=page, total_pages=total_pages)

@orders_bp.route("/orders/edit/<int:order_id>", methods=["GET", "POST"])
@admin_required
def edit_order_items(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        flash("Order not found.", "error")
        cursor.close()
        db.close()
        return redirect(url_for('orders.list_orders'))
        
    if request.method == "POST":
        cursor.execute("SELECT item_id, price FROM food_items")
        food_items_map = {str(f['item_id']): f['price'] for f in cursor.fetchall()}
        
        cursor.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
        total_amount = 0.0
        
        for key, value in request.form.items():
            if key.startswith('qty_'):
                item_id_str = key.replace('qty_', '')
                try:
                    qty = int(value)
                except ValueError:
                    qty = 0
                    
                if qty > 0 and item_id_str in food_items_map:
                    price = float(food_items_map[item_id_str])
                    cursor.execute("SELECT item_name FROM food_items WHERE item_id = %s", (item_id_str,))
                    item_name = cursor.fetchone()['item_name']
                    
                    line_total = price * qty
                    total_amount += line_total
                    
                    cursor.execute(
                        """INSERT INTO order_items (order_id, item_id, item_name, price, quantity)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (order_id, int(item_id_str), item_name, price, qty)
                    )
        
        cursor.execute("UPDATE orders SET total_amount = %s WHERE order_id = %s", (total_amount, order_id))
        db.commit()
        
        flash("Order items updated successfully.", "success")
        cursor.close()
        db.close()
        return redirect(url_for('orders.list_orders'))
        
    cursor.execute("""
        SELECT * FROM food_items 
        WHERE is_available = TRUE OR item_id IN (SELECT item_id FROM order_items WHERE order_id = %s)
        ORDER BY item_name
    """, (order_id,))
    all_food = cursor.fetchall()
    
    cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
    current_items = {item['item_id']: item['quantity'] for item in cursor.fetchall()}
    
    cursor.close()
    db.close()
    return render_template("edit_order_items.html", order=order, all_food=all_food, current_items=current_items)

@orders_bp.route("/orders/view", methods=["GET", "POST"])
@admin_required
def view_order():
    order = None
    items = []
    if request.method == "POST":
        order_id = request.form.get("order_id", "").strip()
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            order_id = int(order_id)
            cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            order = cursor.fetchone()

            if order:
                cursor.execute(
                    "SELECT item_name, price, quantity FROM order_items WHERE order_id = %s",
                    (order["order_id"],)
                )
                items = cursor.fetchall()
            else:
                flash(f"No order found for ID '{order_id}'.", "error")
        except ValueError:
            flash("Please enter a valid Order ID.", "error")

        cursor.close()
        db.close()

    return render_template("view_order.html", order=order, items=items)

@orders_bp.route("/orders/receipt/<int:order_id>")
def print_receipt(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        flash("Order not found.", "error")
        cursor.close()
        db.close()
        return redirect(url_for('orders.list_orders'))
        
    cursor.execute("SELECT item_name, price, quantity FROM order_items WHERE order_id = %s", (order_id,))
    items = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template("receipt.html", order=order, items=items)
@orders_bp.route("/orders/update", methods=["GET", "POST"])
@admin_required
def update_order():
    order = None
    if request.method == "POST":
        action = request.form.get("action")
        db = get_db()
        cursor = db.cursor(dictionary=True)

        if action == "search":
            order_id = request.form.get("order_id", "").strip()
            try:
                order_id = int(order_id)
                cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
                order = cursor.fetchone()
                if not order:
                    flash(f"No order found for ID '{order_id}'.", "error")
            except ValueError:
                flash("Please enter a valid Order ID.", "error")

        elif action == "update":
            order_id = request.form.get("order_id", "").strip()
            new_status = request.form.get("status", "").strip()
            try:
                order_id = int(order_id)
                cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
                order = cursor.fetchone()
                if order:
                    cursor.execute(
                        "UPDATE orders SET status = %s WHERE order_id = %s",
                        (new_status, order_id)
                    )
                    db.commit()
                    flash(f"Order status updated to '{new_status}' for {order['customer_name']}.", "success")
                    try:
                        socketio.emit('kitchen_update', {'action': 'refresh'})
                    except Exception as e:
                        print("SocketIO Error:", e)
                    
                    if order.get('customer_email'):
                        try:
                            msg = Message("Order Status Update", recipients=[order['customer_email']])
                            msg.body = f"Hello {order['customer_name']},\n\nYour order status has been updated to: {new_status}.\n\nThank you!"
                            mail.send(msg)
                        except Exception as e:
                            print("Failed to send email:", e)
                            flash("Status updated, but failed to send email notification.", "warning")
                else:
                    flash("Order not found.", "error")
            except ValueError:
                flash("Invalid Order ID.", "error")

        cursor.close()
        db.close()

    return render_template("update_order.html", order=order)

@orders_bp.route("/orders/cancel", methods=["GET", "POST"])
def cancel_order():
    order = None
    if request.method == "POST":
        action = request.form.get("action")
        db = get_db()
        cursor = db.cursor(dictionary=True)

        if action == "search":
            order_id = request.form.get("order_id", "").strip()
            try:
                order_id = int(order_id)
                cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
                order = cursor.fetchone()
                if not order:
                    flash(f"No order found for ID '{order_id}'.", "error")
            except ValueError:
                flash("Please enter a valid Order ID.", "error")

        elif action == "cancel":
            order_id = request.form.get("order_id", "").strip()
            try:
                order_id = int(order_id)
                cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
                order = cursor.fetchone()
                if order:
                    cursor.execute(
                        "UPDATE orders SET status = 'canceled' WHERE order_id = %s",
                        (order_id,)
                    )
                    db.commit()
                    flash(f"Order for {order['customer_name']} has been canceled.", "success")
                    try:
                        socketio.emit('kitchen_update', {'action': 'refresh'})
                    except Exception as e:
                        print("SocketIO Error:", e)
                    
                    if order.get('customer_email'):
                        try:
                            msg = Message("Order Canceled", recipients=[order['customer_email']])
                            msg.body = f"Hello {order['customer_name']},\n\nYour order has been canceled.\n\nSorry for the inconvenience."
                            mail.send(msg)
                        except Exception as e:
                            print("Failed to send email:", e)
                            flash("Order canceled, but failed to send email notification.", "warning")
                else:
                    flash("Order not found.", "error")
            except ValueError:
                flash("Invalid Order ID.", "error")

        cursor.close()
        db.close()

    return render_template("cancel_order.html", order=order)

@orders_bp.route("/kitchen", methods=["GET", "POST"])
def kitchen_dashboard():
    if session.get('role') not in ['admin', 'kitchen']:
        flash("Access Denied: Kitchen privileges required.", "error")
        return redirect(url_for('public.home'))
        
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == "POST":
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        if order_id and new_status in ['preparing', 'ready']:
            cursor.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
            db.commit()
            try:
                socketio.emit('kitchen_update', {'action': 'refresh'})
            except Exception as e:
                print("SocketIO Error:", e)
            
    cursor.execute("""
        SELECT order_id, order_date, status, customer_name
        FROM orders 
        WHERE status IN ('new', 'preparing')
        ORDER BY order_id ASC
    """)
    orders = cursor.fetchall()
    
    order_items = {}
    if orders:
        order_ids = [str(o['order_id']) for o in orders]
        format_strings = ','.join(['%s'] * len(order_ids))
        cursor.execute(f"SELECT order_id, item_name, quantity FROM order_items WHERE order_id IN ({format_strings})", tuple(order_ids))
        items = cursor.fetchall()
        for item in items:
            oid = item['order_id']
            if oid not in order_items:
                order_items[oid] = []
            order_items[oid].append(item)
            
    cursor.close()
    db.close()
    
    return render_template("kitchen.html", orders=orders, order_items=order_items)
