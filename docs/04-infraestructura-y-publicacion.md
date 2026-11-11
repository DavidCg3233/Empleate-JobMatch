# 4. Infraestructura y publicación

Esta guía explica dónde vive la aplicación publicada, cómo se conectan GitHub, Railway y Vercel, qué pasa cuando
alguien la abre y cuando se publica un cambio, y cómo operarla en el día a día.

Para crear todo esto desde cero, paso a paso, consulta [DESPLIEGUE.md](../DESPLIEGUE.md).

> Guía anterior: [3. Cómo funciona por dentro](03-como-funciona-por-dentro.md) · Siguiente: [5. Trabajo local y cambios](05-trabajo-local-y-cambios.md)

## Contenido

- [Mapa general](#mapa-general)
- [Las direcciones](#las-direcciones)
- [GitHub: el código](#github-el-código)
- [Railway: el backend y la base de datos](#railway-el-backend-y-la-base-de-datos)
- [Vercel: las páginas](#vercel-las-páginas)
- [Qué pasa cuando alguien abre la app](#qué-pasa-cuando-alguien-abre-la-app)
- [Qué pasa cuando se publica un cambio](#qué-pasa-cuando-se-publica-un-cambio)
- [Local y producción, separados](#local-y-producción-separados)
- [Operación diaria](#operación-diaria)
- [Costos](#costos)
- [Problemas conocidos y soluciones](#problemas-conocidos-y-soluciones)
- [Limitaciones de la infraestructura actual](#limitaciones-de-la-infraestructura-actual)

## Mapa general

```mermaid
flowchart LR
    subgraph PC[Tu computador]
        CODE[Código del proyecto]
    end
    subgraph GH[GitHub]
        REPO[Repositorio, rama main]
    end
    subgraph VC[Vercel]
        FE[Páginas: carpeta frontend]
    end
    subgraph RW[Railway, proyecto production]
        BE[Servicio Empleate-JobMatch: backend FastAPI]
        VOL1[(Volumen: hojas de vida)]
        DB[(Servicio MySQL)]
        VOL2[(Volumen: datos de MySQL)]
    end
    AI[OpenAI]
    U[Persona en su navegador]

    CODE -- git push --> REPO
    REPO -- despliega frontend/ --> FE
    REPO -- despliega backend/ --> BE
    U -- abre la app --> FE
    FE -- reenvía /api --> BE
    BE -- red privada --> DB
    BE --- VOL1
    DB --- VOL2
    BE -- opcional --> AI
```

| Pieza | Servicio | Qué contiene |
|---|---|---|
| **Código** | GitHub | Todo el proyecto, sin secretos ni datos |
| **Páginas** | Vercel | La carpeta `frontend/` |
| **API** | Railway, servicio `Empleate-JobMatch` | La carpeta `backend/`, construida con Docker |
| **Base de datos** | Railway, servicio `MySQL` | La base `jobmatch` con todos los datos |
| **Archivos** | Railway, volumen del backend | Las hojas de vida subidas |
| **IA** | OpenAI | Recibe peticiones del backend, si la IA está activa |

## Las direcciones

| Dirección | Qué es | ¿Para personas? |
|---|---|---|
| https://empleate-jobmatch-frontend.vercel.app | **La app** | Sí: es la que se comparte |
| https://empleate-jobmatch-production.up.railway.app | El backend (solo API) | No. Su raíz responde `{"detail":"Not Found"}`, y es normal |
| `mysql.railway.internal` | MySQL dentro de la red privada de Railway | No: solo la alcanza el backend |
| https://github.com/DavidCg3233/Empleate-JobMatch | El código | Para quien desarrolla |

Direcciones útiles del backend, también a través de Vercel:

| Ruta | Para qué |
|---|---|
| `/api/health` | Comprobar que el backend y la base de datos responden: `{"status":"ok","database":"connected"}` |
| `/api/matching/status` | Ver si la IA está activa: `{"provider":"openai",...}` |
| `/docs` | Documentación interactiva de la API (solo en la dirección de Railway) |

## GitHub: el código

- El código vive en la rama **`main`**.
- **GitHub guarda código, no datos:** ni usuarios, ni vacantes, ni hojas de vida.
- Tampoco guarda secretos: `.env` está en `.gitignore`.
- Railway y Vercel están conectados al repositorio y **se actualizan solos cada vez que llega código nuevo a `main`**.

## Railway: el backend y la base de datos

Railway aloja dos servicios en el entorno **production** del proyecto:

```mermaid
flowchart TB
    subgraph Railway[Proyecto en Railway]
        subgraph S1[Servicio Empleate-JobMatch]
            B[Contenedor Docker con FastAPI]
            V1[(Volumen en /app/uploads)]
        end
        subgraph S2[Servicio MySQL]
            M[MySQL 8.4]
            V2[(Volumen con los datos)]
        end
        B -- mysql.railway.internal:3306 --> M
    end
    Internet((Internet)) -- dominio público, puerto 8000 --> B
```

### Servicio `Empleate-JobMatch` (backend)

| Ajuste | Valor | Por qué |
|---|---|---|
| Origen | Repositorio de GitHub, rama `main` | Se despliega solo con cada cambio |
| **Root Directory** | `backend` | Solo construye esa carpeta |
| Construcción | `backend/Dockerfile` | Railway lo detecta: en los registros aparece `Using detected Dockerfile!` |
| Puerto | `8000` | El que usa Uvicorn |
| Dominio público | `empleate-jobmatch-production.up.railway.app` | Para que Vercel pueda llegar al backend |
| Volumen | Montado en `/app/uploads` | Las hojas de vida sobreviven a cada despliegue |
| Serverless | Activado | Se duerme sin uso para ahorrar saldo; ver [Problemas conocidos](#problemas-conocidos-y-soluciones) |

**Qué hace el `Dockerfile`, paso a paso:**

1. Parte de una imagen con **Python 3.14**.
2. Copia `requirements.txt` e instala las librerías.
3. Copia el resto de `backend/`, sin lo que excluye `.dockerignore`: `.env`, `venv/`, `uploads/` y `tests/`.
4. Arranca **Uvicorn** con `main:app` en el puerto de la variable `PORT`.
5. Usa `--proxy-headers` para conocer la IP real de cada visitante detrás de Vercel y Railway. Sin eso, el límite de
   intentos por IP sería el mismo para todos.

Como solo se copia `backend/`, en Railway no existe la carpeta `frontend/`: por eso ese servicio no sirve páginas.

**Variables del backend** (en la pestaña **Variables**):

| Variable | Valor | Nota |
|---|---|---|
| `DB_HOST` | `${{MySQL.MYSQLHOST}}` | Referencia: Railway pone la dirección privada de MySQL |
| `DB_PORT` | `${{MySQL.MYSQLPORT}}` | Referencia |
| `DB_USER` | `${{MySQL.MYSQLUSER}}` | Referencia |
| `DB_PASSWORD` | `${{MySQL.MYSQLPASSWORD}}` | Referencia: la contraseña nunca se escribe a mano |
| `DB_NAME` | `jobmatch` | La base que crea el script SQL |
| `JWT_SECRET` | Clave larga y aleatoria | Secreta |
| `PORT` | `8000` | |
| `MAX_CV_MB` | `4` | Por el límite de tamaño de peticiones de Vercel |
| `AI_PROVIDER` | `openai` | `none` para apagar la IA |
| `OPENAI_API_KEY` | Clave de OpenAI | Secreta |
| `FRONTEND_URL` | `https://empleate-jobmatch-frontend.vercel.app` | Para armar el enlace de recuperación de contraseña |

Las referencias `${{MySQL....}}` significan que, si Railway cambia algún dato de MySQL, el backend lo recibe solo.

### Servicio `MySQL` (base de datos)

| Ajuste | Valor | Por qué |
|---|---|---|
| Plantilla | MySQL de Railway (8.4) | |
| Base usada | `jobmatch` | La crea `Empleate JObMatch database.sql`. Railway también trae una base `railway` vacía que la app no usa |
| Volumen | Datos de MySQL | La información sobrevive a reinicios |
| Red privada | `mysql.railway.internal` | El backend se conecta por aquí |
| Acceso público | **Desactivado** | Solo se activa unos minutos para tareas manuales |
| Serverless | **Desactivado** | Railway no lo recomienda para bases de datos |

### Red privada y red pública

**Red privada (private networking):** una red interna del proyecto. Los servicios se hablan sin salir a internet,
como las extensiones telefónicas de una empresa. Nadie de afuera puede usar `mysql.railway.internal`.

**Red pública:** direcciones a las que cualquiera puede llegar desde internet.

| Conexión | Tipo | Estado |
|---|---|---|
| Backend → MySQL | Privada | Siempre |
| Internet → Backend | Pública (dominio `.up.railway.app`) | Siempre: Vercel la necesita |
| Tu computador → MySQL | Pública (TCP proxy, `MYSQL_PUBLIC_URL`) | Solo mientras haces una tarea manual |

Quitar la dirección pública de MySQL (el icono de basura en **Settings > Networking**) **no borra datos**: solo
cierra esa puerta.

## Vercel: las páginas

| Ajuste | Valor |
|---|---|
| Origen | Repositorio de GitHub, rama `main` |
| **Root Directory** | `frontend` |
| **Framework Preset** | `Other`: no hay que compilar nada |
| Dirección | `empleate-jobmatch-frontend.vercel.app` |

Vercel sirve los archivos de `frontend/` tal como están. La pieza que conecta todo es `frontend/vercel.json`:

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://empleate-jobmatch-production.up.railway.app/api/:path*" }
  ],
  "headers": [
    {
      "source": "/api/:path*",
      "headers": [{ "key": "x-vercel-enable-rewrite-caching", "value": "0" }]
    }
  ]
}
```

| Parte | Qué hace |
|---|---|
| `rewrites` | Cualquier petición a `/api/...` en Vercel se **reenvía** al backend de Railway. El navegador no se entera: cree que habla solo con Vercel |
| `headers` | Le pide a Vercel no guardar en caché las respuestas de la API, para que los datos estén siempre al día |

**Por qué se hizo así:**

- El navegador habla con **un solo sitio**, así que no hace falta configurar CORS.
- `config.js` usa la dirección de la propia página + `/api`, así que **el mismo código funciona en local y en
  producción**.
- Si el backend cambia de dirección, solo se cambia `vercel.json`.

## Qué pasa cuando alguien abre la app

```mermaid
sequenceDiagram
    participant N as Navegador
    participant V as Vercel
    participant R as Railway: backend
    participant M as Railway: MySQL
    N->>V: GET /pages/auth/login.html
    V-->>N: HTML, CSS y JavaScript
    N->>V: POST /api/auth/login
    V->>R: Reenvía a .../api/auth/login
    R->>M: Consulta el usuario (red privada)
    M-->>R: Datos
    R-->>V: Token de sesión
    V-->>N: Token de sesión
```

1. La persona abre la dirección de Vercel.
2. Vercel entrega las páginas, los estilos y el JavaScript.
3. Cuando la página necesita datos, llama a `/api/...` **en Vercel**.
4. Vercel reenvía esa petición al backend en Railway.
5. El backend consulta MySQL por la red privada y, si hace falta, la IA.
6. La respuesta recorre el camino de vuelta.

## Qué pasa cuando se publica un cambio

```mermaid
flowchart LR
    A[git push a main] --> B[GitHub]
    B --> C[Vercel publica frontend/ en segundos]
    B --> D[Railway construye backend/ con Docker]
    D --> E[Arranca el contenedor nuevo]
    E --> F[Cambia el tráfico al nuevo]
```

| Paso | Vercel | Railway |
|---|---|---|
| Detecta el cambio | Sí, en `main` | Sí, en `main` |
| Qué construye | Nada: copia `frontend/` | Una imagen Docker con `backend/` |
| Tiempo habitual | Menos de un minuto | Unos minutos |
| Interrupción | Ninguna | El servicio con volumen se detiene unos instantes |

**Lo que el push NO actualiza:**

| Qué | Cómo se actualiza |
|---|---|
| **Tablas de la base de datos** | Ejecutando la migración contra la base de Railway **antes** de subir el código (ver [guía 5](05-trabajo-local-y-cambios.md#cambios-en-la-base-de-datos)) |
| **Variables de entorno** | A mano, en Railway |
| **Datos y archivos** | No viajan: cada entorno tiene los suyos |

Si Vercel genera una página de prueba para otra rama (preview), esa página **sigue llamando al backend de
producción**, porque usa el mismo `vercel.json`.

## Local y producción, separados

| | En tu computador | En producción |
|---|---|---|
| Dirección | http://127.0.0.1:8000 | https://empleate-jobmatch-frontend.vercel.app |
| Páginas | Las sirve el mismo backend | Vercel |
| Backend | `uvicorn` en tu equipo | Railway |
| Base de datos | Tu MySQL local | MySQL de Railway |
| Archivos | `backend/uploads/` | Volumen de Railway |
| Configuración | `backend/.env` | Variables de Railway |
| Se actualiza | Al guardar archivos | Al llegar código a `main` |

Las dos bases de datos no están conectadas. Puedes probar todo en local sin afectar a nadie.

## Operación diaria

### Comprobar que la app funciona

1. Abre https://empleate-jobmatch-frontend.vercel.app/api/health.
2. Debe decir `{"status":"ok","database":"connected"}`.

### Ver lo que pasa en el backend

En Railway, en el recuadro `Empleate-JobMatch`:

| Pestaña | Qué muestra |
|---|---|
| **Deployments** | Cada despliegue y si está activo |
| **Deploy Logs** | Peticiones y errores. Un error del servidor aparece como un bloque que empieza con `Traceback` |
| **HTTP Logs** | Cada petición con su código de respuesta |
| **Metrics** | CPU, memoria y tráfico de red |

Los registros se pueden descargar en JSON para revisarlos con calma.

### Consultar la base de datos

| Forma | Cómo | Cuándo |
|---|---|---|
| **Pestaña Database de Railway** | Recuadro MySQL → **Database → Data**. Escribe la tabla con su base: `SELECT * FROM jobmatch.jobs LIMIT 20;` | Consultas rápidas desde el navegador |
| **MySQL Workbench** | Activa **Public Access**, conéctate con los datos de `MYSQL_PUBLIC_URL`, ejecuta `USE jobmatch;` y al terminar borra la dirección pública | Consultas largas |
| **CLI de Railway** | `railway connect MySQL --tunnel-only` abre un túnel privado para Workbench sin acceso público | Uso frecuente |

**Cuidado:** es la base real. Usa `SELECT` para mirar. Antes de un `UPDATE` o `DELETE`, revisa con un `SELECT` qué
filas afecta y nunca los uses sin `WHERE`. La pestaña muestra "You have no tables" porque mira la base `railway`, no
`jobmatch`; tus tablas siguen ahí.

### Ejecutar un script contra producción

Para tareas como crear el administrador o aplicar una migración:

1. Activa **Public Access** en MySQL y copia `MYSQL_PUBLIC_URL`, que tiene la forma
   `mysql://USUARIO:CLAVE@HOST:PUERTO/railway`.
2. Abre una ventana nueva de PowerShell en `backend/` y conéctala a Railway:

   ```powershell
   $env:DB_HOST='HOST'; $env:DB_PORT='PUERTO'; $env:DB_USER='USUARIO'; $env:DB_PASSWORD='CLAVE'; $env:DB_NAME='jobmatch'
   ```

3. Ejecuta el script, por ejemplo `.\venv\Scripts\python.exe -m scripts.migrate_match_stages`.
4. **Cierra esa ventana** para no seguir conectado a producción.
5. **Borra la dirección pública** de MySQL.

Esas variables solo duran en esa ventana y tienen prioridad sobre tu `.env`, que no cambia.

### Copias de seguridad

El recuadro MySQL tiene una pestaña **Backups**. Revisa qué permite tu plan y programa copias antes de recibir datos
reales.

## Costos

Railway cobra por lo que consumen los servicios encendidos. Según su documentación (revisa los
[precios actuales](https://railway.com/pricing)):

| Concepto | Referencia |
|---|---|
| Prueba gratis | Crédito único de $5 que dura 30 días o hasta gastarse, lo que pase primero |
| Plan Hobby | $5 al mes, con $5 de uso incluido |
| Memoria | Unos $10 por GB al mes |
| CPU | Unos $20 por vCPU al mes |
| Al terminar la prueba sin pasar a Hobby | Los servicios se detienen y los volúmenes de cuentas de prueba se borran 30 días después |

Formas de ahorrar:

- **Serverless en el backend:** se duerme sin uso. En MySQL se deja desactivado.
- **Acceso público de MySQL apagado:** su tráfico se cobra.
- **IA:** cada hoja de vida y cada análisis nuevo gastan saldo de OpenAI, que se paga aparte. Conviene poner un límite
  mensual en la cuenta de OpenAI.

Vercel solo sirve archivos estáticos y reenvía la API. Para una prueba pequeña, su plan gratuito suele ser
suficiente; revisa los límites de tu cuenta.

## Problemas conocidos y soluciones

Todos estos casos ocurrieron durante la publicación de la beta:

| Síntoma | Causa | Solución |
|---|---|---|
| La primera petición tras un rato sin uso da **502** y luego funciona | El backend estaba dormido por Serverless y estaba despertando | Normal con Serverless. Antes de una presentación, desactívalo y abre la app |
| Error **500** con `Can't connect to MySQL server on 'mysql.railway.internal' (Connection refused)` | MySQL estaba dormido o reiniciando | Desactivar Serverless en MySQL |
| Error **500** con `Data truncated for column 'stage'` | La columna `stage` quedó con un tipo equivocado | Ejecutar `python -m scripts.migrate_match_stages`, que corrige el tipo |
| La dirección de Railway muestra `{"detail":"Not Found"}` | Es la API, no la app | Usar la dirección de Vercel |
| Las páginas cargan pero no se puede iniciar sesión | `vercel.json` apunta a una dirección equivocada | Corregir el `destination` de `vercel.json` |
| `/api/health` responde 500 | Base de datos sin tablas o `DB_NAME` incorrecto | Ejecutar el script SQL y revisar `DB_NAME=jobmatch` |
| La pestaña Database dice "You have no tables" | Mira la base `railway` | Consultar con el prefijo `jobmatch.` |
| La IA aparece desactivada (`"provider":null`) | Falta o está mal `AI_PROVIDER` u `OPENAI_API_KEY` | `AI_PROVIDER=openai` y la clave en su propia variable; luego desplegar |
| Las hojas de vida desaparecen al redesplegar | El volumen no está montado | Montar el volumen en `/app/uploads` |
| Una petición falla y el detalle no se ve | El error real solo queda en el servidor | Revisar **Deploy Logs** y buscar `Traceback` |

## Limitaciones de la infraestructura actual

| Limitación | Efecto | Posible solución |
|---|---|---|
| Railway bloquea SMTP en el plan Hobby | El enlace de recuperación queda en los registros y no llega al usuario | Enviar correos con un servicio por HTTPS |
| Serverless en el backend | La primera petición después de un rato puede fallar | Desactivarlo cuando se necesite disponibilidad inmediata |
| Una sola instancia con volumen | No se puede escalar a varias copias del backend | Guardar archivos en un almacenamiento externo |
| Límites por IP en memoria | Se reinician con cada despliegue | Guardarlos en una base compartida |
| `/docs` es pública | Cualquiera ve la lista de rutas, aunque no los datos | Desactivarla en producción |
| Límite de peticiones de Vercel | Hojas de vida de hasta 4 MB | Subir archivos directo al backend |
| Copias de seguridad | No están configuradas | Programarlas en la pestaña **Backups** |
