from flask import Flask, jsonify, request
import os
import certifi
import pytds
import requests
import traceback
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
            row_strategy=pytds.namedtuple_row_strategy,
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


@app.route('/api/procesar', methods=['POST'])
def procesar_catalogo():
    try:
        api_key_recibida = request.headers.get('X-API-Key')
        api_key_esperada = os.environ.get("PROCESS_API_KEY")

        if not api_key_recibida or api_key_recibida != api_key_esperada:
            return jsonify({"message": "API Key no válida"}), 401

        data = request.get_json(silent=True) or {}
        correo_destino = data.get('email') or os.environ.get("EMAIL_DESTINO")

        if not correo_destino:
            return jsonify({"message": "Falta el correo de destino"}), 400

        conn = getConnection()
        cursor = conn.cursor()
        cursor.execute("SELECT names, price FROM products_vw")
        
        filas = cursor.fetchall()
        total_productos = len(filas)
        
        texto_productos = "Reporte Oficial de Inventario\n\n"
        texto_productos += "Estimado(a) administrador(a),\n\n"
        texto_productos += "Se ha generado con éxito el reporte actualizado del catálogo de productos registrado en el sistema. A continuación, se detalla la lista vigente con sus respectivos precios:\n\n"

        for row in filas:
            nombre = row.names
            precio = row.price
            texto_productos += f"- 📦 {nombre} — Precio: ${precio}\n"

        texto_productos += f"\nResumen del Sistema:\n"
        texto_productos += f"- Total de productos registrados: {total_productos}\n"
        texto_productos += f"- Estado del proceso: Finalizado con éxito\n\n"
        texto_productos += "Este es un mensaje generado automáticamente por la plataforma de Aplicaciones Distribuidas. Por favor, no responda a este correo."

        cursor.close()
        conn.close()

        brevo_api_key = os.environ.get("BREVO_API_KEY")
        correo_remitente = os.environ.get("EMAIL_REMITENTE")

        if not brevo_api_key or not correo_remitente:
            return jsonify({"message": "Faltan configurar las credenciales de Brevo en el servidor"}), 500

        datos_brevo = {
            "sender": {"name": "Administrador UTA", "email": correo_remitente},
            "replyTo": {"name": "Administrador UTA", "email": correo_remitente},
            "to": [{"email": correo_destino}],
            "subject": "📦 Reporte Oficial: Inventario y Catálogo de Productos",
            "textContent": texto_productos
        }

        respuesta_brevo = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'accept': 'application/json',
                'api-key': brevo_api_key.strip(),
                'content-type': 'application/json'
            },
            json=datos_brevo,
            timeout=20
        )

        if respuesta_brevo.status_code in [200, 201]:
            return jsonify({
                "procesamiento": "finalizado",
                "total_productos": total_productos,
                "notificacion": "enviado"
            }), 200
        else:
            return jsonify({
                "message": "Error al enviar correo en Brevo", 
                "error": respuesta_brevo.text
            }), 500

    except Exception as e:
        error_detallado = traceback.format_exc()
        print("ERROR EN /api/procesar:", error_detallado)
        return jsonify({"message": "Error interno en el servidor", "error": str(e)}), 500
if __name__ == '__main__':
    app.run(
        host='0.0.0.0', port=5000, debug=True
    )
