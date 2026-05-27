# 🔌 red_bt — Plugin QGIS

> Plugin QGIS para el trazado de redes eléctricas de baja tensión con snapping automático a la red existente.  
> Desarrollado para la cooperativa eléctrica de la zona Colonia Caroya / Jesús María, Córdoba, Argentina.

---

## 📋 Descripción

`red_bt` facilita la digitalización de redes de baja tensión en QGIS, con snapping inteligente a postes y nodos de la red de media tensión. Está diseñado para trabajar en conjunto con las capas generadas por `crear_red_electrica`.

**Características principales:**
- Snapping automático a postes y nodos de la red MT preexistente
- Trazado de tramos BT con asignación de sección y tipo de conductor
- Vinculación automática a transformadores de distribución
- Asignación de cargas por tramo
- Capas vectoriales exportables a shapefile / GeoPackage

---

## 🛠️ Requisitos

| Requisito | Versión mínima |
|---|---|
| QGIS | 3.22 LTR |
| Python | 3.9+ |

> Requiere tener cargadas en el proyecto QGIS las capas generadas por `crear_red_electrica` (postes y red MT) para que el snapping funcione correctamente.

---

## 🚀 Instalación

1. Clonar o descargar el repositorio:

```bash
git clone https://github.com/ricardo32vm/crear-red-bt.git
```

2. Copiar la carpeta `red_bt` a la carpeta de plugins de QGIS:

```
# Windows
%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\

# Linux
~/.local/share/QGIS/QGIS3\profiles\default\python\plugins\
```

3. En QGIS → **Complementos** → **Administrar e instalar complementos** → activar **Red BT**.

---

## 📁 Estructura

```
red_bt/
├── __init__.py
├── red_bt.py
├── red_bt_dialog.py
├── metadata.txt
└── resources/
    ├── icons/
    └── ui/
```

---

## 💡 Uso básico

1. Cargar primero las capas de red MT (postes y líneas) generadas con `crear_red_electrica`
2. Activar el plugin desde la barra de herramientas o el menú **Complementos**
3. El snapping se activa automáticamente sobre los nodos de la red MT
4. Trazar los tramos de BT y completar atributos (sección, conductor, carga)
5. Exportar para usar con `shp_a_pandapower`

---

## 🔗 Plugins relacionados

| Plugin | Descripción |
|---|---|
| [`crear_red_electrica`](https://github.com/ricardo32vm/crear-red-electrica) | Trazado de red MT — genera las capas base que usa este plugin |
| [`shp_a_pandapower`](https://github.com/ricardo32vm/shp_a_pandapower) | Convierte ambas redes a un modelo ejecutable en pandapower |

---

## 🗺️ Contexto de aplicación

Herramienta desarrollada para la gestión del área de concesión de la cooperativa eléctrica de **Colonia Caroya / Jesús María**, Provincia de Córdoba, Argentina.

---

## 👨‍💻 Autor

**[Ing. Ricardo Luis castro]**  
Docente-investigador — UTN Facultad Regional Villa María  
📍 Villa María, Córdoba, Argentina

---

## 📄 Licencia

[GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html) — compatible con la licencia estándar de plugins QGIS.
