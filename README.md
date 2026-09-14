# 🤖 ComplyTools - ML & Scraping Engine

Este repositorio contiene el microservicio de **Inteligencia Artificial y Extracción de Datos** del ecosistema ComplyTools. Está construido con **Python y FastAPI**, y se encarga de ejecutar los algoritmos predictivos (Scoring de Riesgos) y las arañas de extracción (Web Scraping) para validar usuarios en listas negativas y listas PEP.

Esta API es consumida de forma interna por el Backend principal de Kotlin.

## 🏗️ Arquitectura del Proyecto

El proyecto está diseñado para ser altamente modular y separar las responsabilidades matemáticas de las funciones de red:

```text
security-machine-learning/
├── app/
│   ├── api/                 # Endpoints y controladores REST de FastAPI
│   ├── core/                # Configuraciones globales (CORS, variables de entorno)
│   ├── ml_engine/           # Motor de Machine Learning
│   │   ├── models/          # Modelos entrenados (Scikit-Learn)
│   │   └── preprocessing/   # Limpieza y transformación de datos (Pandas)
│   ├── scraper/             # Arañas de extracción web (BeautifulSoup)
│   │   ├── listas_pep/      
│   │   └── sanciones/       
│   └── services/            # Casos de uso y lógica de orquestación
├── venv/                    # Entorno virtual aislado (Ignorado en Git)
├── .gitignore
├── main.py                  # Punto de entrada del servidor Uvicorn
└── requirements.txt         # Dependencias y librerías del proyecto

```
🛑 ALTO: Requisitos Previos
Para ejecutar este motor en tu computadora, debes tener instalado:

Python (v3.10 o superior): Asegúrate de marcar la casilla "Add Python to PATH" durante la instalación.

Visual Studio Code: El editor recomendado para trabajar con Python.

🛠️ Paso a paso para levantar el proyecto localmente

Paso 1:

Clonar el proyecto
Abre tu terminal y descarga el código:

Bash
git clone <URL_DEL_REPO_AQUI>
cd security-machine-learning

Paso 2:

Crear y Activar el Entorno Virtual (venv)
Para evitar conflictos con otras instalaciones de Python en tu PC, usaremos un entorno virtual.
En la terminal (preferiblemente PowerShell si usas Windows), ejecuta:

En Windows:

PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
(Nota: Si PowerShell te bloquea el script, ejecuta primero Set-ExecutionPolicy Unrestricted -Scope CurrentUser).

En Mac / Linux:

Bash
python3 -m venv venv
source venv/bin/activate
✅ Sabrás que funcionó si ves un (venv) al inicio de tu línea de comandos. Nunca pases al siguiente paso sin ver ese (venv).


Paso 3:

Instalar las dependencias
Con el entorno virtual activado, instala las librerías matemáticas y de servidor:

Bash
python -m ensurepip --upgrade
python -m pip install -r requirements.txt

Paso 4: 

Levantar el servidor de FastAPI
Arranca el proyecto con este comando:

Bash
python -m uvicorn main:app --reload
✅ ¿Cómo probar la API?
A diferencia de otros lenguajes, FastAPI genera su propia documentación interactiva.
Abre tu navegador web y entra a http://localhost:8000/docs.
Verás la interfaz de Swagger UI donde podrás probar los endpoints de Machine Learning sin necesidad de Postman.

 Flujo de Trabajo para el Equipo (Git Flow)
Nunca trabajes directamente en la rama main.

Actualiza tu entorno local: git pull origin main.

Crea una rama para tu tarea: git checkout -b feature/scraper-pep.

Haz tus cambios y súbelos:

Bash
git add .
git commit -m "feat: agrega araña básica para extraer listas de sanciones"
git push origin feature/scraper-pep
