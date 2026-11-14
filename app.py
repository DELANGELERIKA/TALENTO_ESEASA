
from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from uuid import uuid4
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secreto123"

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Edelangel20",
    database="talento_eseasa"
)


cursor = conexion.cursor()
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']

        sql = "SELECT * FROM usuarios WHERE usuario=%s AND password=%s"
        cursor.execute(sql, (usuario, password))
        user = cursor.fetchone()

        if user:
            session['usuario'] = usuario
            return redirect('/')
        else:
            return "Usuario o contraseña incorrectos"

    return render_template('login.html')

@app.route('/')
def inicio():
    if 'usuario' not in session:
        return redirect('/login')

    busqueda = request.args.get('busqueda')

    if busqueda and busqueda.strip() != "":
        sql = """
            SELECT 
                id_candidato,
                nombre,
                telefono,
                correo,
                ciudad,
                escolaridad,
                especialidad,
                disponibilidad,
                cv_archivo
            FROM candidatos
            WHERE nombre LIKE %s 
            OR especialidad LIKE %s 
            OR ciudad LIKE %s
        """
        valores = (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%")
        cursor.execute(sql, valores)
    else:
        cursor.execute("""
            SELECT 
                id_candidato,
                nombre,
                telefono,
                correo,
                ciudad,
                escolaridad,
                especialidad,
                disponibilidad,
                cv_archivo
            FROM candidatos
        """)

    candidatos = cursor.fetchall()
    return render_template('index.html', candidatos=candidatos)

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect('/login')

@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    telefono = request.form['telefono']
    correo = request.form['correo']
    ciudad = request.form['ciudad']
    escolaridad = request.form['escolaridad']
    especialidad = request.form['especialidad']
    disponibilidad = request.form['disponibilidad']

    archivo = request.files['cv']

    ruta_archivo = ""

    if archivo:
        ruta_archivo = "static/cv/" + archivo.filename
        archivo.save(ruta_archivo)

    sql = """INSERT INTO candidatos 
    (nombre, telefono, correo, ciudad, escolaridad, especialidad, disponibilidad, fecha_registro, cv_archivo) 
    VALUES (%s,%s,%s,%s,%s,%s,%s, NOW(), %s)"""

    valores = (nombre, telefono, correo, ciudad, escolaridad, especialidad, disponibilidad, ruta_archivo)

    cursor.execute(sql, valores)
    conexion.commit()

    return redirect('/')

@app.route('/eliminar/<int:id>')
def eliminar(id):

    # Primero borrar relaciones con vacantes
    cursor.execute(
        "DELETE FROM candidato_vacante WHERE id_candidato = %s",
        (id,)
    )

    # Luego borrar candidato
    cursor.execute(
        "DELETE FROM candidatos WHERE id_candidato = %s",
        (id,)
    )

    conexion.commit()

    return redirect('/')

@app.route('/editar/<int:id>')
def editar(id):
    sql = "SELECT * FROM candidatos WHERE id_candidato=%s"
    cursor.execute(sql, (id,))
    candidato = cursor.fetchone()
    return render_template('editar.html', c=candidato)

@app.route('/actualizar/<int:id>', methods=['POST'])
def actualizar(id):
    nombre = request.form['nombre']
    telefono = request.form['telefono']
    correo = request.form['correo']
    ciudad = request.form['ciudad']
    escolaridad = request.form['escolaridad']
    especialidad = request.form['especialidad']
    disponibilidad = request.form['disponibilidad']

    # Recibir el PDF seleccionado
    archivo = request.files.get('cv_archivo')

    nombre_cv = None

    if archivo and archivo.filename:

        # Verificar que sea un archivo PDF
        nombre_original = secure_filename(archivo.filename)

        if not nombre_original.lower().endswith('.pdf'):
            return "Error: Solo se permiten archivos PDF", 400

        # Crear la carpeta si no existe
        carpeta_cv = os.path.join(app.static_folder, 'cv')
        os.makedirs(carpeta_cv, exist_ok=True)

        # Generar un nombre único para evitar sobrescribir archivos
        nombre_cv = f"{uuid4().hex}_{nombre_original}"

        ruta_cv = os.path.join(carpeta_cv, nombre_cv)

        # Guardar el nuevo PDF
        archivo.save(ruta_cv)

    if nombre_cv:

        # Actualizar datos y nuevo CV
        sql = """
        UPDATE candidatos SET
            nombre=%s,
            telefono=%s,
            correo=%s,
            ciudad=%s,
            escolaridad=%s,
            especialidad=%s,
            disponibilidad=%s,
            cv_archivo=%s
        WHERE id_candidato=%s
        """

        valores = (
            nombre, telefono, correo, ciudad,
            escolaridad, especialidad,
            disponibilidad, nombre_cv, id
        )

    else:

        # Actualizar datos sin modificar el CV existente
        sql = """
        UPDATE candidatos SET
            nombre=%s,
            telefono=%s,
            correo=%s,
            ciudad=%s,
            escolaridad=%s,
            especialidad=%s,
            disponibilidad=%s
        WHERE id_candidato=%s
        """

        valores = (
            nombre, telefono, correo, ciudad,
            escolaridad, especialidad,
            disponibilidad, id
        )

    cursor.execute(sql, valores)
    conexion.commit()

    return redirect('/')


@app.route('/sugerir/<int:id_vacante>')
def sugerir(id_vacante):
    # obtener vacante
    cursor.execute("SELECT * FROM vacantes_futuras WHERE id_vacante=%s", (id_vacante,))
    vacante = cursor.fetchone()

    puesto = vacante[1]

    # buscar candidatos por coincidencia en especialidad
    sql = """SELECT * FROM candidatos 
             WHERE especialidad LIKE %s"""
    cursor.execute(sql, (f"%{puesto}%",))
    candidatos = cursor.fetchall()

    return render_template('sugerencias.html', candidatos=candidatos, vacante=vacante)

@app.route('/asignar/<int:id_candidato>/<int:id_vacante>')
def asignar(id_candidato, id_vacante):
    sql = """
    INSERT INTO candidato_vacante (id_candidato, id_vacante, estatus)
    VALUES (%s, %s, 'Pendiente')
    """
    cursor.execute(sql, (id_candidato, id_vacante))
    conexion.commit()
    return redirect('/vacantes')

@app.route('/vacantes')
def vacantes():

    sql = """
    SELECT 
        v.id_vacante,
        v.puesto,
        v.fecha_estimada,
        v.cantidad,
        v.prioridad,
        v.descripcion,
        COUNT(c.id_candidato) AS total_candidatos
    FROM vacantes_futuras v
    LEFT JOIN candidato_vacante cv 
        ON v.id_vacante = cv.id_vacante
    LEFT JOIN candidatos c
        ON cv.id_candidato = c.id_candidato
    GROUP BY 
        v.id_vacante,
        v.puesto,
        v.fecha_estimada,
        v.cantidad,
        v.prioridad,
        v.descripcion
    """

    cursor.execute(sql)
    vacantes = cursor.fetchall()

    return render_template('vacantes.html', vacantes=vacantes)

@app.route('/guardar_vacante', methods=['POST'])
def guardar_vacante():
    puesto = request.form['puesto']
    fecha = request.form['fecha']
    cantidad = request.form['cantidad']
    prioridad = request.form['prioridad']
    descripcion = request.form['descripcion']

    sql = """INSERT INTO vacantes_futuras 
    (puesto, fecha_estimada, cantidad, prioridad, descripcion)
    VALUES (%s,%s,%s,%s,%s)"""

    valores = (puesto, fecha, cantidad, prioridad, descripcion)

    cursor.execute(sql, valores)
    conexion.commit()

    return redirect('/vacantes')

@app.route('/ver_asignados/<int:id_vacante>')
def ver_asignados(id_vacante):

    # 🔹 obtener vacante
    cursor.execute("SELECT * FROM vacantes_futuras WHERE id_vacante=%s", (id_vacante,))
    vacante = cursor.fetchone()

    # 🔹 obtener candidatos
    sql = """
    SELECT c.nombre, c.especialidad, c.ciudad, c.cv_archivo, cv.estatus, cv.id
    FROM candidato_vacante cv
    JOIN candidatos c ON cv.id_candidato = c.id_candidato
    WHERE cv.id_vacante = %s
    """
    
    cursor.execute(sql, (id_vacante,))
    candidatos = cursor.fetchall()

    return render_template('asignados.html', candidatos=candidatos, vacante=vacante)

@app.route('/estatus/<int:id>/<nuevo>')
def cambiar_estatus(id, nuevo):

    sql = """
    UPDATE candidato_vacante
    SET estatus = %s
    WHERE id = %s
    """

    cursor.execute(sql, (nuevo, id))
    conexion.commit()

    return redirect(request.referrer)

@app.route('/eliminar_asignacion/<int:id>')
def eliminar_asignacion(id):

    sql = """
    DELETE FROM candidato_vacante
    WHERE id = %s
    """

    cursor.execute(sql, (id,))
    conexion.commit()

    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)