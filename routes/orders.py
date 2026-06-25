from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import date
from flask_mail import Message
from database import get_db
from extensions import mail
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
                msg.body = f"Hello {customer_name},\n\nYour order has been placed successfully!\nTotal amount: Rs {total_amount:.2f}\n\nPlease find your bill attached.\n\nThank you for ordering with us."
                
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center;">
                        <h2 style="margin: 0;">Order Confirmed!</h2>
                    </div>
                    <div style="padding: 20px; color: #333;">
                        <p style="font-size: 16px;">Hello <strong>{customer_name}</strong>,</p>
                        <p style="font-size: 16px;">Thank you for your order! Your order has been placed successfully.</p>
                        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <h3 style="margin-top: 0; color: #4CAF50;">Order Summary</h3>
                            <p style="margin: 5px 0;"><strong>Order ID:</strong> #{order_id}</p>
                            <p style="margin: 5px 0;"><strong>Total Amount:</strong> Rs {total_amount:.2f}</p>
                        </div>
                        <p style="font-size: 16px;">Please find your detailed bill attached to this email.</p>
                    </div>
                    <div style="background-color: #f1f1f1; color: #777; padding: 10px; text-align: center; font-size: 12px;">
                        &copy; 2026 Restaurant Name. All rights reserved.
                    </div>
                </div>
                """
                msg.html = html_body
                
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Helvetica", style="B", size=20)
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(0, 15, text="RESTAURANT NAME", align="C", new_x="LMARGIN", new_y="NEXT", fill=True)
                pdf.ln(5)
                
                pdf.set_font("Helvetica", size=12)
                pdf.cell(0, 8, text="ORDER RECEIPT", align="C", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 6, text=f"Order #: {order_id} | Date: {order_date}", align="C", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(5)
                
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", style="B", size=11)
                pdf.cell(30, 8, text="Customer:", align="L")
                pdf.set_font("Helvetica", size=11)
                pdf.cell(0, 8, text=f"{customer_name}", align="L", new_x="LMARGIN", new_y="NEXT")
                
                pdf.set_font("Helvetica", style="B", size=11)
                pdf.cell(30, 8, text="Mobile:", align="L")
                pdf.set_font("Helvetica", size=11)
                pdf.cell(0, 8, text=f"{customer_mobile}", align="L", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(8)
                
                pdf.set_fill_color(50, 50, 50)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", style="B", size=11)
                pdf.cell(100, 10, text=" Item Description", align="L", fill=True)
                pdf.cell(30, 10, text="Qty", align="C", fill=True)
                pdf.cell(60, 10, text="Total ", align="R", new_x="LMARGIN", new_y="NEXT", fill=True)
                
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", size=11)
                fill = False
                pdf.set_fill_color(245, 245, 245)
                
                for item_id, item_name, price, qty in selected_items:
                    line_total = float(price) * qty
                    clean_item_name = str(item_name).encode('latin-1', 'replace').decode('latin-1')
                    pdf.cell(100, 10, text=f" {clean_item_name[:40]}", align="L", fill=fill)
                    pdf.cell(30, 10, text=f"{qty}x", align="C", fill=fill)
                    pdf.cell(60, 10, text=f"Rs {line_total:.2f} ", align="R", new_x="LMARGIN", new_y="NEXT", fill=fill)
                    fill = not fill
                
                pdf.ln(5)
                pdf.set_font("Helvetica", style="B", size=14)
                pdf.cell(130, 12, text="TOTAL AMOUNT:", align="R")
                pdf.set_text_color(40, 167, 69)
                pdf.cell(60, 12, text=f"Rs {total_amount:.2f} ", align="R", new_x="LMARGIN", new_y="NEXT")
                
                pdf.ln(15)
                pdf.set_text_color(150, 150, 150)
                pdf.set_font("Helvetica", style="I", size=10)
                pdf.cell(0, 10, text="Thank you for your business!", align="C", new_x="LMARGIN", new_y="NEXT")
                
                pdf_bytes = pdf.output()
                msg.attach(f"receipt_order_{order_id}.pdf", "application/pdf", bytes(pdf_bytes))
                
                mail.send(msg)
            except Exception as e:
                print("Failed to send email:", e)
                flash("Order created but failed to send email. Check SMTP settings.", "warning")

        flash(f"Order #{order_id} created successfully for {customer_name}.", "success")

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

                    
                    if order.get('customer_email'):
                        try:
                            cursor.execute("SELECT item_name, price, quantity FROM order_items WHERE order_id = %s", (order_id,))
                            selected_items = cursor.fetchall()
                            
                            msg = Message("Order Canceled", recipients=[order['customer_email']])
                            msg.body = f"Hello {order['customer_name']},\n\nYour order #{order_id} has been canceled.\n\nSorry for the inconvenience."
                            
                            html_body = f"""
                            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                                <div style="background-color: #f44336; color: white; padding: 20px; text-align: center;">
                                    <h2 style="margin: 0;">Order Canceled</h2>
                                </div>
                                <div style="padding: 20px; color: #333;">
                                    <p style="font-size: 16px;">Hello <strong>{order['customer_name']}</strong>,</p>
                                    <p style="font-size: 16px;">We are writing to inform you that your order <strong>#{order_id}</strong> has been canceled.</p>
                                    <p style="font-size: 16px;">Please find your canceled bill attached to this email.</p>
                                    <p style="font-size: 16px;">We sincerely apologize for any inconvenience this may have caused. If you have any questions or concerns, please don't hesitate to reach out to us.</p>
                                    <br>
                                    <p style="font-size: 16px;">Best regards,<br><strong>Restaurant Team</strong></p>
                                </div>
                                <div style="background-color: #f1f1f1; color: #777; padding: 10px; text-align: center; font-size: 12px;">
                                    &copy; 2026 Restaurant Name. All rights reserved.
                                </div>
                            </div>
                            """
                            msg.html = html_body
                            
                            from fpdf import FPDF
                            pdf = FPDF()
                            pdf.add_page()
                            
                            pdf.set_font("Helvetica", style="B", size=80)
                            pdf.set_text_color(255, 200, 200)
                            
                            x_center = 105
                            y_center = 148.5
                            width = pdf.get_string_width("CANCELLED")
                            
                            with pdf.rotation(45, x_center, y_center):
                                pdf.text(x=x_center - width/2, y=y_center + 10, text='CANCELLED')
                                
                            pdf.set_font("Helvetica", style="B", size=20)
                            pdf.set_fill_color(240, 240, 240)
                            pdf.set_text_color(0, 0, 0)
                            pdf.cell(0, 15, text="RESTAURANT NAME", align="C", new_x="LMARGIN", new_y="NEXT", fill=True)
                            pdf.ln(5)
                            
                            pdf.set_font("Helvetica", size=12)
                            pdf.cell(0, 8, text="CANCELED ORDER RECEIPT", align="C", new_x="LMARGIN", new_y="NEXT")
                            pdf.set_text_color(100, 100, 100)
                            pdf.cell(0, 6, text=f"Order #: {order_id} | Date: {order['order_date']}", align="C", new_x="LMARGIN", new_y="NEXT")
                            pdf.ln(5)
                            
                            pdf.set_text_color(0, 0, 0)
                            pdf.set_font("Helvetica", style="B", size=11)
                            pdf.cell(30, 8, text="Customer:", align="L")
                            pdf.set_font("Helvetica", size=11)
                            pdf.cell(0, 8, text=f"{order['customer_name']}", align="L", new_x="LMARGIN", new_y="NEXT")
                            
                            pdf.set_font("Helvetica", style="B", size=11)
                            pdf.cell(30, 8, text="Mobile:", align="L")
                            pdf.set_font("Helvetica", size=11)
                            pdf.cell(0, 8, text=f"{order['customer_mobile']}", align="L", new_x="LMARGIN", new_y="NEXT")
                            pdf.ln(8)
                            
                            pdf.set_fill_color(50, 50, 50)
                            pdf.set_text_color(255, 255, 255)
                            pdf.set_font("Helvetica", style="B", size=11)
                            pdf.cell(100, 10, text=" Item Description", align="L", fill=True)
                            pdf.cell(30, 10, text="Qty", align="C", fill=True)
                            pdf.cell(60, 10, text="Total ", align="R", new_x="LMARGIN", new_y="NEXT", fill=True)
                            
                            pdf.set_text_color(0, 0, 0)
                            pdf.set_font("Helvetica", size=11)
                            fill = False
                            pdf.set_fill_color(245, 245, 245)
                            
                            for item in selected_items:
                                item_name = item['item_name']
                                price = item['price']
                                qty = item['quantity']
                                line_total = float(price) * qty
                                clean_item_name = str(item_name).encode('latin-1', 'replace').decode('latin-1')
                                pdf.cell(100, 10, text=f" {clean_item_name[:40]}", align="L", fill=fill)
                                pdf.cell(30, 10, text=f"{qty}x", align="C", fill=fill)
                                pdf.cell(60, 10, text=f"Rs {line_total:.2f} ", align="R", new_x="LMARGIN", new_y="NEXT", fill=fill)
                                fill = not fill
                            
                            pdf.ln(5)
                            pdf.set_font("Helvetica", style="B", size=14)
                            pdf.cell(130, 12, text="TOTAL AMOUNT:", align="R")
                            pdf.set_text_color(220, 53, 69)
                            pdf.cell(60, 12, text=f"Rs {order['total_amount']:.2f} ", align="R", new_x="LMARGIN", new_y="NEXT")
                            
                            pdf.ln(15)
                            pdf.set_text_color(150, 150, 150)
                            pdf.set_font("Helvetica", style="I", size=10)
                            pdf.cell(0, 10, text="This order has been canceled.", align="C", new_x="LMARGIN", new_y="NEXT")
                            
                            pdf_bytes = pdf.output()
                            msg.attach(f"canceled_receipt_{order_id}.pdf", "application/pdf", bytes(pdf_bytes))
                            
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
