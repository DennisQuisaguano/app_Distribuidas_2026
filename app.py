from flask import Flask, jsonify
import os
import certifi
import pytds
from threading import Lock

#Conexion con la base de datos

app  = Flask(__name__)
product_lock = Lock()

def getConnection():
   return pytds.connect(
            server=os.environ.get("DB_SERVER"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            port=1433,
            cafile=certifi.where(),
            validate_host=True,
   )   

@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("SELECT DB_NAME()")
        database = cursor.fetchone()[0]
        conn.close()

        return jsonify(
            {
                "message": "Conexión exitosa a la base de datos", 
                "base de datos": database
            }
        ), 200
    
    except Exception as e:
        return jsonify({"message": "Error al conectar a la base de datos", "error": str(e)}), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute(""" SELECT id, names, price, stock FROM products_vw """)
        products = []
        for row in cursor.fetchall():
            products.append({
                "id" : row.id,
                "names" : row.names,
                "price" : row.price,
                "stock" : row.stock
            })

        return jsonify(products), 200
    

    except Exception as e:
        return jsonify({
            "message": "Error al obtener los productos", 
            "error": str(e)
            }), 500


@app.route('/api/products/<int:id>', methods=['GET'])
def get_product(id):
    try:
        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute(""" SELECT id, names, price, stock FROM products_vw WHERE id = ? """, (id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            return jsonify({
                "id" : row.id,
                "names" : row.names,
                "price" : row.price,
                "stock" : row.stock
            }), 200

        return jsonify({
            "message": "Producto no encontrado"
        }), 404

    except Exception as e:
        return jsonify({
            "message": "Error al obtener el producto", 
            "error": str(e)
            }
        ), 404


#sp
@app.route('/api/products', methods=['POST'])
def create_product():
    try:
        data = request.get_json()

        if not data :
            return jsonify({
                "message": "Datos inválidos"
            }), 400

        names = data.get('names')
        price = data.get('price')
        stock = data.get('stock')

        if not names or not price or not stock:
            return jsonify({
                "message": "Datos incompletos"
            }), 400

        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute("EXEC products_insert_sp ?, ?, ?", (names, price, stock))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": "Producto creado exitosamente"
        }), 201

    except Exception as e:
        return jsonify({
            "message": "Error al crear el producto", 
            "error": str(e)

        }),500

##################UPDATE####################}
###SIN CONTROLL

@app.route("/api/products",methods=['PUT'])
def update_products():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Sin data",
            }), 400

        conn = getConnection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE products SET names=?, price=?, stock=? WHERE id=?",
            (data.get('names'), data.get('price'), data.get('stock'), data.get('id'))
        )
        
        if cursor.rowcount == 0:
            conn.rollback()
            cursor.close()
            conn.close()

            return jsonify({
                "message": "registro no encontrado"
            }), 404

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "registro actualizado"
        }), 200

    except Exception as e:
        return jsonify({
            "message": "Error al actualizar", 
            "error": str(e)

        }), 500




@app.route("/api/products/lock",methods=['PUT'])
def update_products_lock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Sin informacion",
            }), 400
        
        with product_lock:
            conn = getConnection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET names=?, price=?, stock=? WHERE id=?",
                (data.get('names'), data.get('price'), data.get('stock'), data.get('id'))
            )
            if cursor.rowcount == 0:
                conn.rollback()
                cursor.close()
                conn.close()
                return jsonify({
                    "message": "registro no encontrado"
                }), 404

            conn.commit()
            cursor.close()
            conn.close()

        return jsonify({
            "message": "Todo OK"
        }), 200
    except Exception as e:
        return jsonify({
            "message": "Error al actualizar", 
            "error": str(e)

        }), 500


@app.route("/api/products/version" , methods=['PUT'])
def update_version():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Datos incompletos",
            }), 400

        
        if data.get('version') is None:
            return jsonify({
                "message": "Faltan parametros (version)",
            }), 400
        
        conn = getConnection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET names=?, price=?, stock=?, version=version+1 WHERE id=? AND version=?",
            (data.get("names"), data.get("price"), data.get('stock'), data.get('id'), data.get('version'))
        )
        
        if cursor.rowcount == 0:
            cursor.execute("select version from products where id=?", data.get('id'))
            row = cursor.fetchone()

            conn.rollback()
            cursor.close()
            conn.close()

            if row :
                producto_actual = {
                    "id": data.get('id'),
                    "version": row.version
                }
                return jsonify({
                    "message": "El producto ya fue actualizado",
                    "producto_actual": producto_actual
                }), 409
            else:
                return jsonify({
                    "message": "Producto no encontrado"
                }), 404
        
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "producto actualizado con exito"
        }), 200

    except Exception as e:
        return jsonify({
            "message": "Error al actualizar", 
            "error": str(e)

        }), 500



if __name__ == '__main__':
    app.run(
        host='0.0.0.0', port=5000, debug=True
    )
