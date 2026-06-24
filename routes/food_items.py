from flask import Blueprint, render_template, request, redirect, url_for, flash
import mysql.connector
import csv
import io
from database import get_db
from routes.auth import admin_required

food_items_bp = Blueprint('food_items', __name__)

@food_items_bp.route("/food-items", methods=["GET", "POST"])
@admin_required
def food_items():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip().title()
        price = request.form.get("price", "").strip()
        category_id = request.form.get("category_id")
        if not category_id: category_id = None
        stock_quantity = request.form.get("stock_quantity", 100)
        is_available = 1 if request.form.get("is_available") else 0

        if not item_name or not price:
            flash("Please provide both item name and price.", "error")
        else:
            try:
                price_val = float(price)
                cursor.execute(
                    "INSERT INTO food_items (item_name, price, category_id, stock_quantity, is_available) VALUES (%s, %s, %s, %s, %s)",
                    (item_name, price_val, category_id, stock_quantity, is_available)
                )
                db.commit()
                flash(f"Food item '{item_name}' added successfully.", "success")
            except mysql.connector.errors.IntegrityError:
                flash(f"Item '{item_name}' already exists.", "error")
            except ValueError:
                flash("Price must be a valid number.", "error")

        return redirect(url_for("food_items.food_items"))

    cursor.execute("SELECT * FROM food_items ORDER BY item_name")
    items = cursor.fetchall()
    cursor.execute("SELECT * FROM categories ORDER BY category_name")
    categories = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("food_items.html", items=items, categories=categories)

@food_items_bp.route("/food-items/edit/<int:item_id>", methods=["GET", "POST"])
@admin_required
def edit_food_item(item_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip().title()
        price = request.form.get("price", "").strip()
        category_id = request.form.get("category_id")
        if not category_id: category_id = None
        stock_quantity = request.form.get("stock_quantity", 100)
        is_available = 1 if request.form.get("is_available") else 0

        if not item_name or not price:
            flash("Please provide both item name and price.", "error")
        else:
            try:
                price_val = float(price)
                cursor.execute(
                    "UPDATE food_items SET item_name = %s, price = %s, category_id = %s, stock_quantity = %s, is_available = %s WHERE item_id = %s",
                    (item_name, price_val, category_id, stock_quantity, is_available, item_id)
                )
                db.commit()
                flash(f"Food item '{item_name}' updated successfully.", "success")
                cursor.close()
                db.close()
                return redirect(url_for("food_items.food_items"))
            except mysql.connector.errors.IntegrityError:
                flash(f"Item '{item_name}' already exists.", "error")
            except ValueError:
                flash("Price must be a valid number.", "error")

    cursor.execute("SELECT * FROM food_items WHERE item_id = %s", (item_id,))
    item = cursor.fetchone()
    
    cursor.execute("SELECT * FROM categories ORDER BY category_name")
    categories = cursor.fetchall()
    
    cursor.close()
    db.close()

    if not item:
        flash("Food item not found.", "error")
        return redirect(url_for("food_items.food_items"))

    return render_template("edit_food_item.html", item=item, categories=categories)

@food_items_bp.route("/food-items/upload-csv", methods=["POST"])
@admin_required
def upload_csv():
    if 'csv_file' not in request.files:
        flash("No file part", "error")
        return redirect(url_for("food_items.food_items"))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No selected file", "error")
        return redirect(url_for("food_items.food_items"))
        
    if file and file.filename.endswith('.csv'):
        # Parse the CSV
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            
            db = get_db()
            cursor = db.cursor()
            
            success_count = 0
            error_count = 0
            
            for row in csv_input:
                if len(row) >= 2:
                    item_name = row[0].strip().title()
                    price_str = row[1].strip()
                    
                    if not item_name or not price_str:
                        continue
                        
                    # Skip header if present (e.g. "Price", "Item Name", etc)
                    if price_str.lower() == 'price' or item_name.lower() == 'food name':
                        continue
                        
                    # Also handle case if the price has currency symbols, just remove common ones
                    price_str = price_str.replace('₹', '').replace('Rs.', '').replace(',', '').strip()
                        
                    try:
                        price_val = float(price_str)
                        cursor.execute(
                            "INSERT IGNORE INTO food_items (item_name, price) VALUES (%s, %s)",
                            (item_name, price_val)
                        )
                        if cursor.rowcount > 0:
                            success_count += 1
                    except ValueError:
                        error_count += 1
                        
            db.commit()
            cursor.close()
            db.close()
            
            if success_count > 0:
                flash(f"Successfully uploaded {success_count} new food items from CSV.", "success")
            if error_count > 0:
                flash(f"Failed to parse {error_count} rows due to invalid data.", "error")
            if success_count == 0 and error_count == 0:
                flash("No valid new items found in CSV (or all were duplicates).", "error")
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "error")
            
    else:
        flash("Please upload a valid .csv file", "error")
        
    return redirect(url_for("food_items.food_items"))
