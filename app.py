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


@app.route('/api/send-catalog-email', methods=['POST'])
def send_catalog_email():
    try:
        data = request.get_json()
        if not data or not data.get('email'):
            return jsonify({"message": "Falta el correo de destino"}), 400
        
        correo_destino = data.get('email')

        # 1. Consultar los productos desde la base de datos
        conn = getConnection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, names, price, stock FROM products_vw")
        
        filas_html = ''
        texto_productos = "Hola,\n\nA continuación te compartimos el listado de productos disponibles:\n\n"
        
        for index, row in enumerate(cursor.fetchall()):
            nombre = getattr(row, 'names', 'Sin nombre')
            precio = getattr(row, 'price', '0.00')
            stock = getattr(row, 'stock', '0')

            texto_productos += f"- {nombre} | Precio: ${precio} | Stock: {stock} unidades\n"
            bg_color = '#ffffff' if index % 2 == 0 else '#f9fbfc'

            filas_html += f'''
            <tr style="background-color: {bg_color};">
                <td style="padding: 12px 15px; border-bottom: 1px solid #e1e8ed; color: #333333; font-weight: 500;">{nombre}</td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #e1e8ed; color: #0284c7; font-weight: bold; text-align: right;">${precio}</td>
                <td style="padding: 12px 15px; border-bottom: 1px solid #e1e8ed; color: #475569; text-align: right;">{stock} unidades</td>
            </tr>'''

        cursor.close()
        conn.close()

        # 2. Diseño HTML profesional para el correo
        contenido_html = f'''
        <div style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 30px 0; margin: 0;">
            <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                <tr>
                    <td style="background-color: #0284c7; padding: 25px; text-align: center; color: #ffffff;">
                        <h2 style="margin: 0; font-size: 22px; font-weight: bold;">📦 Catálogo de Productos</h2>
                        <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Listado oficial actualizado</p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 30px;">
                        <p style="margin-top: 0; color: #333333; font-size: 15px;">Hola,</p>
                        <p style="color: #4b5563; font-size: 15px; line-height: 1.5;">A continuación te compartimos el detalle de los productos disponibles que solicitaste:</p>
                        
                        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; margin-top: 20px; border: 1px solid #e1e8ed; border-radius: 8px; overflow: hidden;">
                            <thead>
                                <tr style="background-color: #f8fafc; color: #1e293b; text-align: left; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">
                                    <th style="padding: 12px 15px; border-bottom: 2px solid #e1e8ed;">Producto</th>
                                    <th style="padding: 12px 15px; border-bottom: 2px solid #e1e8ed; text-align: right;">Precio</th>
                                    <th style="padding: 12px 15px; border-bottom: 2px solid #e1e8ed; text-align: right;">Stock</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_html}
                            </tbody>
                        </table>

                        <p style="margin-top: 25px; color: #64748b; font-size: 13px; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px;">
                            Este es un mensaje automatizado enviado desde tu API Distribuida.
                        </p>
                    </td>
                </tr>
            </table>
        </div>'''

        # 3. Credenciales de Brevo
        brevo_api_key = os.environ.get("BREVO_API_KEY")
        correo_remitente = os.environ.get("BREVO_SENDER_EMAIL")

        if not brevo_api_key or not correo_remitente:
            return jsonify({"message": "Faltan configurar las variables de entorno de Brevo en Render"}), 500

        # Enviamos 'htmlContent' para que llegue con diseño visual
        datos_brevo = {
            "sender": {"name": "Dennis Quisaguano", "email": correo_remitente},
            "replyTo": {"name": "Dennis Quisaguano", "email": correo_remitente},
            "to": [{"email": correo_destino}],
            "subject": "Tu catálogo de productos solicitado",
            "htmlContent": contenido_html,
            "textContent": texto_productos
        }

        # 4. Petición POST a la API de Brevo
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
            return jsonify({"message": "Correo enviado exitosamente"}), 200
        else:
            return jsonify({
                "message": "Brevo rechazó la petición", 
                "error": respuesta_brevo.text
            }), 500

    except Exception as e:
        error_detallado = traceback.format_exc()
        print("ERROR EN SEND-CATALOG-EMAIL:", error_detallado)
        return jsonify({"message": "Error interno en el servidor", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(
        host='0.0.0.0', port=5000, debug=True
    )
