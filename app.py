from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, date
import os

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Necesario para mensajes flash

DB_NAME = "tareas_pro.db"

# ============================================
# FUNCIONES DE BASE DE DATOS (casi igual que antes)
# ============================================

def crear_tabla():
    """Crea las tablas si no existen"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # Tabla de categorías
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '🔵'
        )
    ''')
    
    # Tabla de tareas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            fecha_limite DATE,
            categoria_id INTEGER,
            completada BOOLEAN DEFAULT 0,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id)
        )
    ''')
    
    # Categorías por defecto
    categorias_default = [
        ('Personal', '🔴'),
        ('Trabajo', '🔵'),
        ('Estudio', '🟢'),
        ('Compras', '🟡')
    ]
    
    for cat in categorias_default:
        try:
            cursor.execute("INSERT INTO categorias (nombre, color) VALUES (?, ?)", cat)
        except sqlite3.IntegrityError:
            pass
    
    conexion.commit()
    conexion.close()

def obtener_tareas(filtro=None, valor=None, busqueda=None):
    """Obtiene las tareas según filtros"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    query = '''
        SELECT t.id, t.descripcion, t.fecha_limite, 
               c.nombre, c.color, t.completada,
               c.id as cat_id
        FROM tareas t
        LEFT JOIN categorias c ON t.categoria_id = c.id
    '''
    
    params = []
    
    if busqueda:
        query += " WHERE LOWER(t.descripcion) LIKE ?"
        params.append(f'%{busqueda.lower()}%')
    elif filtro == "categoria":
        query += " WHERE c.id = ?"
        params.append(valor)
    elif filtro == "completadas":
        query += " WHERE t.completada = 1"
    elif filtro == "pendientes":
        query += " WHERE t.completada = 0"
    elif filtro == "vencidas":
        query += " WHERE t.fecha_limite < date('now') AND t.completada = 0"
    
    query += " ORDER BY t.completada ASC, t.fecha_limite ASC, t.id DESC"
    
    cursor.execute(query, params)
    tareas = cursor.fetchall()
    conexion.close()
    
    # Procesar fechas para mostrar días restantes
    hoy = date.today()
    tareas_procesadas = []
    
    for t in tareas:
        tarea = list(t)
        if t[2]:  # Si tiene fecha
            try:
                fecha = datetime.strptime(t[2], '%Y-%m-%d').date()
                dias = (fecha - hoy).days
                tarea.append(dias)  # días restantes
                
                if dias < 0 and not t[5]:
                    tarea.append('vencida')
                elif dias == 0 and not t[5]:
                    tarea.append('hoy')
                elif dias <= 3 and not t[5]:
                    tarea.append('urge')
                else:
                    tarea.append('normal')
            except:
                tarea.append(999)
                tarea.append('normal')
        else:
            tarea.append(999)  # días restantes (infinito)
            tarea.append('normal')
        
        tareas_procesadas.append(tarea)
    
    return tareas_procesadas

def obtener_categorias():
    """Obtiene todas las categorías"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre, color FROM categorias ORDER BY nombre")
    categorias = cursor.fetchall()
    conexion.close()
    return categorias

# ============================================
# RUTAS WEB (¡aquí ocurre la magia!)
# ============================================

@app.route('/')
def index():
    """Página principal - muestra todas las tareas"""
    crear_tabla()  # Asegurar que existe la BD
    tareas = obtener_tareas()
    categorias = obtener_categorias()
    return render_template('index.html', 
                         tareas=tareas, 
                         categorias=categorias,
                         filtro_activo='todas')

@app.route('/agregar', methods=['POST'])
def agregar():
    """Añade una nueva tarea"""
    descripcion = request.form['descripcion']
    fecha_limite = request.form.get('fecha_limite', '')
    categoria_id = request.form.get('categoria_id')
    
    if not descripcion:
        flash('❌ La descripción no puede estar vacía', 'error')
        return redirect(url_for('index'))
    
    # Convertir fecha vacía a None
    if not fecha_limite:
        fecha_limite = None
    
    # Convertir categoría vacía a None
    if not categoria_id:
        categoria_id = None
    
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute('''
        INSERT INTO tareas (descripcion, fecha_limite, categoria_id) 
        VALUES (?, ?, ?)
    ''', (descripcion, fecha_limite, categoria_id))
    conexion.commit()
    conexion.close()
    
    flash('✅ Tarea agregada con éxito', 'success')
    return redirect(url_for('index'))

@app.route('/completar/<int:id>')
def completar(id):
    """Marca una tarea como completada"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (id,))
    conexion.commit()
    conexion.close()
    
    flash('✅ Tarea completada!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/descompletar/<int:id>')
def descompletar(id):
    """Marca una tarea como no completada"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("UPDATE tareas SET completada = 0 WHERE id = ?", (id,))
    conexion.commit()
    conexion.close()
    
    flash('🔄 Tarea reactivada', 'info')
    return redirect(request.referrer or url_for('index'))

@app.route('/borrar/<int:id>')
def borrar(id):
    """Elimina una tarea"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM tareas WHERE id = ?", (id,))
    conexion.commit()
    conexion.close()
    
    flash('🗑️ Tarea eliminada', 'info')
    return redirect(request.referrer or url_for('index'))

@app.route('/filtrar')
def filtrar():
    """Aplica filtros a las tareas"""
    filtro = request.args.get('filtro', 'todas')
    valor = request.args.get('valor', None)
    
    if filtro == 'categoria' and valor:
        tareas = obtener_tareas(filtro='categoria', valor=valor)
    elif filtro == 'completadas':
        tareas = obtener_tareas(filtro='completadas')
    elif filtro == 'pendientes':
        tareas = obtener_tareas(filtro='pendientes')
    elif filtro == 'vencidas':
        tareas = obtener_tareas(filtro='vencidas')
    else:
        tareas = obtener_tareas()
    
    categorias = obtener_categorias()
    return render_template('index.html', 
                         tareas=tareas, 
                         categorias=categorias,
                         filtro_activo=filtro,
                         categoria_activa=valor)

@app.route('/buscar')
def buscar():
    """Busca tareas por palabra clave"""
    query = request.args.get('q', '')
    if query:
        tareas = obtener_tareas(busqueda=query)
    else:
        tareas = obtener_tareas()
    
    categorias = obtener_categorias()
    return render_template('index.html', 
                         tareas=tareas, 
                         categorias=categorias,
                         busqueda=query)

@app.route('/categoria/nueva', methods=['POST'])
def nueva_categoria():
    """Crea una nueva categoría"""
    nombre = request.form['nombre']
    color = request.form.get('color', '🔵')
    
    if not nombre:
        flash('❌ El nombre no puede estar vacío', 'error')
        return redirect(url_for('index'))
    
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    try:
        cursor.execute("INSERT INTO categorias (nombre, color) VALUES (?, ?)", 
                      (nombre, color))
        conexion.commit()
        flash(f'✅ Categoría {color} {nombre} creada!', 'success')
    except sqlite3.IntegrityError:
        flash(f'❌ Ya existe una categoría llamada {nombre}', 'error')
    
    conexion.close()
    return redirect(url_for('index'))

@app.route('/categoria/borrar/<int:id>')
def borrar_categoria(id):
    """Borra una categoría (solo si no tiene tareas)"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # Verificar si hay tareas usando esta categoría
    cursor.execute("SELECT COUNT(*) FROM tareas WHERE categoria_id = ?", (id,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        flash('❌ No se puede borrar: hay tareas usando esta categoría', 'error')
    else:
        cursor.execute("DELETE FROM categorias WHERE id = ?", (id,))
        conexion.commit()
        flash('🗑️ Categoría eliminada', 'success')
    
    conexion.close()
    return redirect(url_for('index'))

# ============================================
# PUNTO DE ENTRADA (modificado para producción)
# ============================================
if __name__ == '__main__':
    crear_tabla()
    # Esto solo se ejecuta en desarrollo local
    app.run(debug=True, host='0.0.0.0', port=5000)
# Para producción, Render usará gunicorn (definido en Procfile)