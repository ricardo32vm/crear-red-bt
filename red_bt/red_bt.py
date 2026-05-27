import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsPointXY,
    QgsSpatialIndex,
    edit
)

CRS = "EPSG:22174"

# -----------------------------------------------------------------------
# Tabla de prefijos de autonumeración: nombre_capa -> (campo_id, prefijo)
# -----------------------------------------------------------------------
ID_PREFIX = {
    "nodos_bt":        ("id_nodo",   "N"),
    "apr_bt":          ("id",        "APR"),
    "medidores_bt":    ("id",        "M"),
    "lineas_bt":       ("id",        "LBT"),
    "acometidas_bt":   ("id",        "ACO"),
}

# Campo que almacena el identificador en cada capa de puntos/líneas
ID_FIELD = {
    "nodos_bt":     "id_nodo",
    "apr_bt":       "id",
    "medidores_bt": "id",
}

# Capas que pueden ser nodo_inicial de una línea BT
CAPAS_NODO_INICIAL_LBT = ["nodos_bt", "apr_bt", "subestaciones_bt"]

# Capas que pueden ser nodo_inicial de una acometida (nodos BT o APR)
CAPAS_NODO_INICIAL_ACO = ["nodos_bt", "apr_bt"]

# Capa que es nodo_final de una acometida (siempre medidor)
CAPA_NODO_FINAL_ACO = "medidores_bt"


class RedBTPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self.action_nodo       = None
        self.action_apr        = None
        self.action_medidor    = None
        self.action_linea_bt   = None
        self.action_acometida  = None

        self.nodos_layer      = None
        self.apr_layer        = None
        self.medidores_layer  = None
        self.lineas_layer     = None
        self.acometidas_layer = None

        # Subestaciones de MT que pueden ser nodo_inicial de líneas BT
        # (capa externa, solo lectura)
        self.subestaciones_mt_layer = None

        # Índices espaciales por capa
        self._indices = {}

        self.plugin_dir = os.path.dirname(__file__)

    # ------------------------------------------------------------------
    # QGIS lifecycle
    # ------------------------------------------------------------------

    def initGui(self):
        def icon(name):
            return QIcon(os.path.join(self.plugin_dir, "icons", name))

        self.action_nodo = QAction(
            icon("icon_nodo.svg"), "Crear Nodos BT", self.iface.mainWindow())
        self.action_nodo.setToolTip("Inicializa la capa de nodos de baja tensión y activa el editor")
        self.action_nodo.triggered.connect(self.activar_nodos)

        self.action_apr = QAction(
            icon("icon_apr.svg"), "Crear APR (Seccionadores BT)", self.iface.mainWindow())
        self.action_apr.setToolTip("Inicializa la capa de APR y activa el editor")
        self.action_apr.triggered.connect(self.activar_apr)

        self.action_medidor = QAction(
            icon("icon_medidor.svg"), "Crear Medidores", self.iface.mainWindow())
        self.action_medidor.setToolTip("Inicializa la capa de medidores y activa el editor")
        self.action_medidor.triggered.connect(self.activar_medidores)

        self.action_linea_bt = QAction(
            icon("icon_linea_bt.svg"), "Crear Líneas BT", self.iface.mainWindow())
        self.action_linea_bt.setToolTip(
            "Activa el editor de líneas BT (requiere al menos 2 elementos en la red)")
        self.action_linea_bt.setEnabled(False)
        self.action_linea_bt.triggered.connect(self.activar_lineas_bt)

        self.action_acometida = QAction(
            icon("icon_acometida.svg"), "Crear Acometidas", self.iface.mainWindow())
        self.action_acometida.setToolTip(
            "Activa el editor de acometidas (requiere al menos 1 nodo/APR y 1 medidor)")
        self.action_acometida.setEnabled(False)
        self.action_acometida.triggered.connect(self.activar_acometidas)

        for action in (
            self.action_nodo,
            self.action_apr,
            self.action_medidor,
            self.action_linea_bt,
            self.action_acometida,
        ):
            self.iface.addToolBarIcon(action)
            self.iface.addPluginToMenu("Red BT", action)

    def unload(self):
        for action in (
            self.action_nodo,
            self.action_apr,
            self.action_medidor,
            self.action_linea_bt,
            self.action_acometida,
        ):
            if action:
                self.iface.removeToolBarIcon(action)
                self.iface.removePluginMenu("Red BT", action)

    # ------------------------------------------------------------------
    # Definición de capas
    # ------------------------------------------------------------------

    def _crear_capa_nodos(self):
        layer = QgsVectorLayer(f"Point?crs={CRS}", "nodos_bt", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id_nodo",  QVariant.String),
            QgsField("coord_x",  QVariant.Double),
            QgsField("coord_y",  QVariant.Double),
        ])
        layer.updateFields()
        return layer

    def _crear_capa_apr(self):
        layer = QgsVectorLayer(f"Point?crs={CRS}", "apr_bt", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id",               QVariant.String),
            QgsField("tipo_seccionador", QVariant.String),
            QgsField("end_line",         QVariant.String),
            QgsField("start_line",       QVariant.String),
        ])
        layer.updateFields()
        return layer

    def _crear_capa_medidores(self):
        layer = QgsVectorLayer(f"Point?crs={CRS}", "medidores_bt", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id",            QVariant.String),
            QgsField("tipo_medidor",  QVariant.String),
            QgsField("numero",        QVariant.String),
            QgsField("acometida_end", QVariant.String),
        ])
        layer.updateFields()
        return layer

    def _crear_capa_lineas_bt(self):
        layer = QgsVectorLayer(f"LineString?crs={CRS}", "lineas_bt", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id",           QVariant.String),
            QgsField("nodo_inicial", QVariant.String),
            QgsField("nodo_final",   QVariant.String),
            QgsField("tipo_linea",   QVariant.String),
            QgsField("longitud",     QVariant.Double),
            QgsField("seccion",      QVariant.String),
        ])
        layer.updateFields()
        return layer

    def _crear_capa_acometidas(self):
        layer = QgsVectorLayer(f"LineString?crs={CRS}", "acometidas_bt", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("id",           QVariant.String),
            QgsField("nodo_inicial", QVariant.String),
            QgsField("nodo_final",   QVariant.String),
        ])
        layer.updateFields()
        return layer

    # ------------------------------------------------------------------
    # Activación de capas (helper genérico)
    # ------------------------------------------------------------------

    def _activar_capa_puntos(self, nombre_capa, factory, callback):
        existing = QgsProject.instance().mapLayersByName(nombre_capa)
        if existing:
            layer = existing[0]
        else:
            layer = factory()
            QgsProject.instance().addMapLayer(layer)

        try:
            layer.featureAdded.disconnect(callback)
        except Exception:
            pass
        layer.featureAdded.connect(callback)

        self.iface.setActiveLayer(layer)
        layer.startEditing()
        self.iface.actionAddFeature().trigger()
        return layer

    def activar_nodos(self):
        self.nodos_layer = self._activar_capa_puntos(
            "nodos_bt", self._crear_capa_nodos, self._on_nodo_agregado)
        self._actualizar_botones()

    def activar_apr(self):
        self.apr_layer = self._activar_capa_puntos(
            "apr_bt", self._crear_capa_apr, self._on_apr_agregado)
        self._actualizar_botones()

    def activar_medidores(self):
        self.medidores_layer = self._activar_capa_puntos(
            "medidores_bt", self._crear_capa_medidores, self._on_medidor_agregado)
        self._actualizar_botones()

    def activar_lineas_bt(self):
        if self._total_nodos_red() < 2:
            QMessageBox.warning(
                None, "Red BT",
                "Debe digitalizar al menos 2 elementos (nodos, APR o subestaciones MT) "
                "antes de crear líneas BT."
            )
            return

        existing = QgsProject.instance().mapLayersByName("lineas_bt")
        if existing:
            self.lineas_layer = existing[0]
        else:
            self.lineas_layer = self._crear_capa_lineas_bt()
            QgsProject.instance().addMapLayer(self.lineas_layer)

        try:
            self.lineas_layer.featureAdded.disconnect(self._on_linea_bt_agregada)
        except Exception:
            pass
        self.lineas_layer.featureAdded.connect(self._on_linea_bt_agregada)

        self._reconstruir_indices()

        self.iface.setActiveLayer(self.lineas_layer)
        self.lineas_layer.startEditing()
        self.iface.actionAddFeature().trigger()

    def activar_acometidas(self):
        # Verificar que haya al menos un nodo/APR y un medidor
        if self._total_nodos_acometida() < 1 or self._total_medidores() < 1:
            QMessageBox.warning(
                None, "Red BT",
                "Debe existir al menos un nodo o APR (como origen) y "
                "al menos un medidor (como destino) para crear acometidas."
            )
            return

        existing = QgsProject.instance().mapLayersByName("acometidas_bt")
        if existing:
            self.acometidas_layer = existing[0]
        else:
            self.acometidas_layer = self._crear_capa_acometidas()
            QgsProject.instance().addMapLayer(self.acometidas_layer)

        try:
            self.acometidas_layer.featureAdded.disconnect(self._on_acometida_agregada)
        except Exception:
            pass
        self.acometidas_layer.featureAdded.connect(self._on_acometida_agregada)

        self._reconstruir_indices()

        self.iface.setActiveLayer(self.acometidas_layer)
        self.acometidas_layer.startEditing()
        self.iface.actionAddFeature().trigger()

    # ------------------------------------------------------------------
    # Eventos: autonumeración de elementos puntuales
    # ------------------------------------------------------------------

    def _autonumerar(self, layer, nombre_capa, fid):
        id_field, prefix = ID_PREFIX[nombre_capa]
        ids_existentes = []
        for f in layer.getFeatures():
            val = f[id_field]
            if val and str(val).startswith(prefix):
                sufijo = str(val)[len(prefix):]
                try:
                    ids_existentes.append(int(sufijo))
                except ValueError:
                    pass
        next_num = max(ids_existentes) + 1 if ids_existentes else 1
        new_id = f"{prefix}{next_num}"
        layer.changeAttributeValue(fid, layer.fields().indexFromName(id_field), new_id)
        return new_id

    def _on_nodo_agregado(self, fid):
        layer = self.nodos_layer
        self._autonumerar(layer, "nodos_bt", fid)
        feature = layer.getFeature(fid)
        geom = feature.geometry()
        if geom and not geom.isNull():
            point = geom.asPoint()
            layer.changeAttributeValue(
                fid, layer.fields().indexFromName("coord_x"), round(point.x(), 3))
            layer.changeAttributeValue(
                fid, layer.fields().indexFromName("coord_y"), round(point.y(), 3))
        self._actualizar_botones()

    def _on_apr_agregado(self, fid):
        self._autonumerar(self.apr_layer, "apr_bt", fid)
        self._actualizar_botones()

    def _on_medidor_agregado(self, fid):
        self._autonumerar(self.medidores_layer, "medidores_bt", fid)
        self._actualizar_botones()

    # ------------------------------------------------------------------
    # Evento: línea BT agregada
    # ------------------------------------------------------------------

    def _on_linea_bt_agregada(self, fid):
        if not self._indices:
            self._reconstruir_indices()

        layer = self.lineas_layer
        feature = layer.getFeature(fid)
        geom = feature.geometry()
        if not geom or geom.isNull():
            return

        vertices = list(geom.vertices())
        if len(vertices) < 2:
            return

        start_pt = QgsPointXY(vertices[0].x(),  vertices[0].y())
        end_pt   = QgsPointXY(vertices[-1].x(), vertices[-1].y())
        longitud = round(geom.length(), 3)

        # nodo_inicial: buscar en nodos_bt + apr_bt + subestaciones_bt (MT)
        nodo_inicial = self._mas_cercano_en_capas(
            start_pt, ["nodos_bt", "apr_bt", "subestaciones_bt"])

        # nodo_final: buscar en nodos_bt + apr_bt + subestaciones_bt
        nodo_final = self._mas_cercano_en_capas(
            end_pt, ["nodos_bt", "apr_bt", "subestaciones_bt"])

        # Autonumerar línea
        new_id = self._autonumerar_linea(layer, "lineas_bt")

        layer.changeAttributeValue(fid, layer.fields().indexFromName("id"),           new_id)
        layer.changeAttributeValue(fid, layer.fields().indexFromName("nodo_inicial"), nodo_inicial)
        layer.changeAttributeValue(fid, layer.fields().indexFromName("nodo_final"),   nodo_final)
        layer.changeAttributeValue(fid, layer.fields().indexFromName("longitud"),     longitud)

        # Retroalimentar APR (si alguno de los extremos es un APR)
        self._retroalimentar_apr(nodo_inicial, new_id, "start_line")
        self._retroalimentar_apr(nodo_final,   new_id, "end_line")

    # ------------------------------------------------------------------
    # Evento: acometida agregada
    # ------------------------------------------------------------------

    def _on_acometida_agregada(self, fid):
        if not self._indices:
            self._reconstruir_indices()

        layer = self.acometidas_layer
        feature = layer.getFeature(fid)
        geom = feature.geometry()
        if not geom or geom.isNull():
            return

        vertices = list(geom.vertices())
        if len(vertices) < 2:
            return

        start_pt = QgsPointXY(vertices[0].x(),  vertices[0].y())
        end_pt   = QgsPointXY(vertices[-1].x(), vertices[-1].y())

        # nodo_inicial: nodos BT o APR
        nodo_inicial = self._mas_cercano_en_capas(
            start_pt, ["nodos_bt", "apr_bt"])

        # nodo_final: siempre un medidor
        nodo_final = self._mas_cercano_en_capas(
            end_pt, ["medidores_bt"])

        # Autonumerar acometida
        new_id = self._autonumerar_linea(layer, "acometidas_bt")

        layer.changeAttributeValue(fid, layer.fields().indexFromName("id"),           new_id)
        layer.changeAttributeValue(fid, layer.fields().indexFromName("nodo_inicial"), nodo_inicial)
        layer.changeAttributeValue(fid, layer.fields().indexFromName("nodo_final"),   nodo_final)

        # Retroalimentar el medidor: escribir ID de acometida en acometida_end
        self._retroalimentar_medidor(nodo_final, new_id)

    # ------------------------------------------------------------------
    # Índices espaciales
    # ------------------------------------------------------------------

    def _capas_disponibles(self):
        """
        Devuelve dict {nombre_capa: layer} de todas las capas activas,
        incluyendo subestaciones de MT si están en el proyecto.
        """
        mapa = {
            "nodos_bt":     self.nodos_layer,
            "apr_bt":       self.apr_layer,
            "medidores_bt": self.medidores_layer,
        }
        # Intentar resolver desde el proyecto si la referencia interna es None
        for nombre in list(mapa.keys()):
            if mapa[nombre] is None:
                existing = QgsProject.instance().mapLayersByName(nombre)
                if existing:
                    mapa[nombre] = existing[0]

        # Subestaciones de MT (capa externa, sin referencia propia)
        if "subestaciones_bt" not in mapa or mapa.get("subestaciones_bt") is None:
            existing = QgsProject.instance().mapLayersByName("subestaciones")
            if existing:
                mapa["subestaciones_bt"] = existing[0]

        return {k: v for k, v in mapa.items() if v is not None}

    def _reconstruir_indices(self):
        self._indices = {}
        for nombre, layer in self._capas_disponibles().items():
            self._indices[nombre] = QgsSpatialIndex(layer.getFeatures())

    def _mas_cercano_en_capas(self, punto: QgsPointXY, nombres_capas: list) -> str:
        """
        Busca el elemento más cercano al punto entre las capas indicadas.
        Devuelve el ID del elemento (string).
        """
        mejor_id   = ""
        mejor_dist = float("inf")
        capas = self._capas_disponibles()

        for nombre in nombres_capas:
            layer = capas.get(nombre)
            if layer is None:
                continue
            idx = self._indices.get(nombre)
            if idx is None:
                continue
            nearest = idx.nearestNeighbor(punto, 1)
            if not nearest:
                continue
            feat = layer.getFeature(nearest[0])
            geom = feat.geometry()
            if geom is None or geom.isNull():
                continue
            dist = geom.asPoint().distance(punto)
            if dist < mejor_dist:
                mejor_dist = dist
                # Determinar campo ID
                if nombre == "subestaciones_bt":
                    id_field = "id"   # capa de MT usa "id"
                else:
                    id_field = ID_FIELD.get(nombre, "id")
                mejor_id = str(feat[id_field])

        return mejor_id

    # ------------------------------------------------------------------
    # Retroalimentación
    # ------------------------------------------------------------------

    def _retroalimentar_apr(self, elemento_id: str, linea_id: str, campo: str):
        """Si el elemento_id corresponde a un APR, escribe linea_id en su campo."""
        if not elemento_id:
            return
        apr_layer = self._capas_disponibles().get("apr_bt")
        if apr_layer is None:
            return
        for feat in apr_layer.getFeatures():
            if str(feat["id"]) == elemento_id:
                idx = apr_layer.fields().indexFromName(campo)
                if idx >= 0:
                    apr_layer.changeAttributeValue(feat.id(), idx, linea_id)
                return

    def _retroalimentar_medidor(self, medidor_id: str, acometida_id: str):
        """Escribe el ID de la acometida en el campo acometida_end del medidor."""
        if not medidor_id:
            return
        med_layer = self._capas_disponibles().get("medidores_bt")
        if med_layer is None:
            return
        for feat in med_layer.getFeatures():
            if str(feat["id"]) == medidor_id:
                idx = med_layer.fields().indexFromName("acometida_end")
                if idx >= 0:
                    med_layer.changeAttributeValue(feat.id(), idx, acometida_id)
                return

    # ------------------------------------------------------------------
    # Autonumeración de líneas (helper)
    # ------------------------------------------------------------------

    def _autonumerar_linea(self, layer, nombre_capa: str) -> str:
        id_field, prefix = ID_PREFIX[nombre_capa]
        ids_existentes = []
        for f in layer.getFeatures():
            val = f[id_field]
            if val and str(val).startswith(prefix):
                sufijo = str(val)[len(prefix):]
                try:
                    ids_existentes.append(int(sufijo))
                except ValueError:
                    pass
        next_num = max(ids_existentes) + 1 if ids_existentes else 1
        return f"{prefix}{next_num}"

    # ------------------------------------------------------------------
    # Conteos para habilitar botones
    # ------------------------------------------------------------------

    def _total_nodos_red(self) -> int:
        """Nodos + APR + subestaciones MT disponibles."""
        total = 0
        capas = self._capas_disponibles()
        for nombre in ["nodos_bt", "apr_bt", "subestaciones_bt"]:
            layer = capas.get(nombre)
            if layer:
                total += layer.featureCount()
        return total

    def _total_nodos_acometida(self) -> int:
        """Nodos + APR para origen de acometidas."""
        total = 0
        capas = self._capas_disponibles()
        for nombre in ["nodos_bt", "apr_bt"]:
            layer = capas.get(nombre)
            if layer:
                total += layer.featureCount()
        return total

    def _total_medidores(self) -> int:
        layer = self._capas_disponibles().get("medidores_bt")
        return layer.featureCount() if layer else 0

    def _actualizar_botones(self):
        if self.action_linea_bt:
            self.action_linea_bt.setEnabled(self._total_nodos_red() >= 2)
        if self.action_acometida:
            self.action_acometida.setEnabled(
                self._total_nodos_acometida() >= 1 and self._total_medidores() >= 1
            )
