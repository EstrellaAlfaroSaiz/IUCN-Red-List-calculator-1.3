# -*- coding: utf-8 -*-
"""Dialog and UI for the AOO/EOO GBIF plugin."""

from __future__ import annotations

from datetime import datetime
import os
import math
import re

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.PyQt.QtGui import QDesktopServices, QIntValidator
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionDialog
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsMapLayerProxyModel,
    QgsWkbTypes,
    Qgis,
    QgsPointXY,
    QgsVectorLayer,
    QgsFeature,
    QgsField,
)
try:
    from qgis.PyQt.QtCore import QVariant
except ImportError:  # pragma: no cover
    class QVariant:
        String = str
        Int = int
        Double = float
        Bool = bool


SizePolicy = getattr(QSizePolicy, "Policy", QSizePolicy)

def _qt_item_user_checkable():
    try:
        return Qt.ItemIsUserCheckable
    except AttributeError:
        return Qt.ItemFlag.ItemIsUserCheckable


def _qt_checked():
    try:
        return Qt.Checked
    except AttributeError:
        return Qt.CheckState.Checked


def _qt_unchecked():
    try:
        return Qt.Unchecked
    except AttributeError:
        return Qt.CheckState.Unchecked


def _qt_user_role():
    try:
        return Qt.UserRole
    except AttributeError:
        return Qt.ItemDataRole.UserRole


def _qt_item_is_enabled():
    try:
        return Qt.ItemIsEnabled
    except AttributeError:
        return Qt.ItemFlag.ItemIsEnabled


def _qt_item_is_selectable():
    try:
        return Qt.ItemIsSelectable
    except AttributeError:
        return Qt.ItemFlag.ItemIsSelectable


def _dialog_accepted():
    try:
        return QDialog.Accepted
    except AttributeError:
        return QDialog.DialogCode.Accepted


def _dialog_exec(dialog):
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


def _button_box_ok():
    try:
        return QDialogButtonBox.Ok
    except AttributeError:
        return QDialogButtonBox.StandardButton.Ok


def _button_box_cancel():
    try:
        return QDialogButtonBox.Cancel
    except AttributeError:
        return QDialogButtonBox.StandardButton.Cancel




def _set_form_expanding_fields(form):
    """Set QFormLayout growth/wrapping in a Qt5/Qt6-compatible way."""
    try:
        policy = QFormLayout.ExpandingFieldsGrow
    except AttributeError:
        try:
            policy = QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        except AttributeError:
            policy = None
    if policy is not None:
        form.setFieldGrowthPolicy(policy)
    try:
        wrap_policy = QFormLayout.WrapLongRows
    except AttributeError:
        try:
            wrap_policy = QFormLayout.RowWrapPolicy.WrapLongRows
        except AttributeError:
            wrap_policy = None
    if wrap_policy is not None:
        form.setRowWrapPolicy(wrap_policy)



def _messagebox_yes():
    try:
        return QMessageBox.Yes
    except AttributeError:
        return QMessageBox.StandardButton.Yes


def _messagebox_no():
    try:
        return QMessageBox.No
    except AttributeError:
        return QMessageBox.StandardButton.No

def _line_edit_password():
    try:
        return QLineEdit.Password
    except AttributeError:
        return QLineEdit.EchoMode.Password


def _point_layer_filter():
    """QGIS 3.34+ and QGIS 4 moved layer filter enums to Qgis.LayerFilter."""
    try:
        return Qgis.LayerFilter.PointLayer
    except AttributeError:  # QGIS 3.28-3.32
        return QgsMapLayerProxyModel.PointLayer

def _layer_is_usable(layer) -> bool:
    """Return False when a QGIS layer wrapper points to an object already deleted by QGIS."""
    if layer is None:
        return False
    try:
        return layer.isValid()
    except RuntimeError:
        return False


def _layer_name(layer, fallback: str = "") -> str:
    try:
        return layer.name() if layer is not None else fallback
    except RuntimeError:
        return fallback


from .gbif_client import (
    GbifError,
    match_species,
    search_occurrences,
    slim_record,
    publishing_organization_name,
    request_occurrence_download_by_gbif_ids,
    get_occurrence_download,
)
from .manual_point_tool import ManualPointTool, ManualRectangleTool
from .processing_logic import (
    add_manual_feature,
    create_manual_layer,
    create_occurrence_layer,
    import_manual_csv,
    run_aoo_eoo,
    create_report_layers,
    IUCN_POLYGON_FIELD_GUIDE,
    REPORT_FIELD_SPECS,
    EXCLUDED_FIELD_SPECS,
    USED_POINT_FIELD_SPECS,
    create_point_distribution_layer,
    write_point_distribution_csv,
    write_geojson_layers,
    create_point_distribution_shapefile_layer,
    write_point_distribution_shapefile,
    create_gbif_derived_dataset_result_layer,
    create_gbif_occurrence_download_result_layer,
    coordinatecleaner_filter_records,
    create_distribution_range_layer,
)


BASIS_OPTIONS = [
    ("HUMAN_OBSERVATION", True, "Include: human observation; review identity and spatial precision."),
    ("PRESERVED_SPECIMEN", True, "Include with control: vouchers or specimens; review date and georeferencing."),
    ("MACHINE_OBSERVATION", False, "Review: cameras, sensors or automatic identification. Not included by default."),
    ("MATERIAL_SAMPLE", False, "Review: physical or environmental sample."),
    ("MATERIAL_CITATION", False, "Review: material citation; possible duplicate or low precision."),
    ("OCCURRENCE", False, "Review: generic category."),
    ("OBSERVATION", False, "Review: generic category."),
    ("LIVING_SPECIMEN", False, "Excluir por defecto: puede ser ex situ o cultivado."),
    ("FOSSIL_SPECIMEN", False, "Exclude by default for current distribution."),
    ("UNKNOWN", False, "Exclude/Review: unknown record type."),
]

ESTABLISHMENT_OPTIONS = [
    ("NATIVE", True, "Include: native population."),
    ("NATIVE_REINTRODUCED", True, "Include/Review: reintroduction within the native area."),
    ("INTRODUCED", False, "Exclude by default in native-distribution assessment."),
    ("INTRODUCED_ASSISTED_COLONISATION", False, "Exclude/Review depending on objective."),
    ("VAGRANT", False, "Exclude: does not represent stable occupancy."),
    ("UNCERTAIN", False, "Revisar: origen incierto."),
]


class ManualFeatureDialog(QDialog):
    """Small form for one user-added occurrence."""

    def __init__(self, parent=None, default_name: str = "", show_coordinates: bool = False, map_point=None, map_crs=None):
        super().__init__(parent)
        self.show_coordinates = show_coordinates
        title = "Add point by coordinates" if show_coordinates else "Add user point for AOO/EOO"
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        _set_form_expanding_fields(form)

        self.scientific_name = QLineEdit(default_name)
        self.event_date = QLineEdit(datetime.now().strftime("%Y-%m-%d"))

        self.map_point = map_point
        self.map_crs = map_crs
        self.point_crs = QgsCoordinateReferenceSystem("EPSG:4326") if show_coordinates else map_crs
        self.crs_button = QPushButton()
        self.crs_button.clicked.connect(self._choose_point_crs)
        form.addRow("Coordinate CRS (click to change)", self.crs_button)
        if show_coordinates:
            self.x_coord = QDoubleSpinBox()
            self.y_coord = QDoubleSpinBox()
            form.addRow("X / longitude *", self.x_coord)
            form.addRow("Y / latitude *", self.y_coord)
        else:
            self.clicked_coordinates = QLabel()
            form.addRow("Map point (X, Y)", self.clicked_coordinates)
        self._update_point_crs()

        self.data_origin_text = QLineEdit()
        self.data_origin_text.setPlaceholderText("E.g.: fieldwork, herbarium, bibliography, report")
        self.data_curator = QLineEdit()
        self.evidence = QComboBox()
        self.evidence.addItems(["voucher/specimen", "field observation", "photograph", "report", "bibliography", "other"])
        self.identifier = QLineEdit()
        self.uncertainty = QDoubleSpinBox()
        self.uncertainty.setRange(0, 1_000_000)
        self.uncertainty.setDecimals(2)
        self.uncertainty.setValue(4)
        self.uncertainty.setSuffix(" m")
        self.review = QComboBox()
        self.review.addItems(["Accepted", "Review before use", "Excluded"])
        self.include = QCheckBox("Use this point in the calculation")
        self.include.setChecked(True)
        self.notes = QLineEdit()

        form.addRow("Taxon", self.scientific_name)
        form.addRow("Date", self.event_date)
        form.addRow("Data source", self.data_origin_text)
        form.addRow("Data curator", self.data_curator)
        form.addRow("Evidence", self.evidence)
        form.addRow("Identifier (voucher number or other ID)", self.identifier)
        form.addRow("Uncertainty", self.uncertainty)
        form.addRow("Decision for this point", self.review)
        form.addRow("Calculation", self.include)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(_button_box_ok() | _button_box_cancel())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_point_crs(self):
        selector = QgsProjectionSelectionDialog(self)
        selector.setCrs(self.point_crs)
        if _dialog_exec(selector) == _dialog_accepted() and selector.crs().isValid():
            previous = self.point_crs
            self.point_crs = selector.crs()
            try:
                self._update_point_crs()
            except (RuntimeError, ValueError) as exc:
                self.point_crs = previous
                self._update_point_crs()
                QMessageBox.warning(self, "Coordinate CRS", str(exc))

    def point_in_selected_crs(self):
        if self.show_coordinates:
            return QgsPointXY(self.x_coord.value(), self.y_coord.value())
        if self.map_crs == self.point_crs:
            return self.map_point
        return QgsCoordinateTransform(self.map_crs, self.point_crs, QgsProject.instance()).transform(self.map_point)

    def _update_point_crs(self):
        crs = self.point_crs
        if self.show_coordinates:
            geographic = crs.isGeographic()
            for field, limit in ((self.x_coord, 180), (self.y_coord, 90)):
                bound = limit if geographic else 1e12
                field.setDecimals(8)
                field.setRange(-bound, bound)
                field.setSingleStep(0.0001 if geographic else 1)
        else:
            point = self.point_in_selected_crs()
            self.clicked_coordinates.setText(f"{point.x():.8f}, {point.y():.8f}")
        self.crs_button.setText(f"{crs.authid()} {crs.description()}".strip())

    def values(self) -> dict:
        review_map = {
            "Review before use": "revisar",
            "Accepted": "aceptado",
            "Excluded": "excluido",
        }
        data_citation = ""
        data_origin = self.data_origin_text.text().strip() or "manual"
        values = {
            "scientificName": self.scientific_name.text().strip(),
            "eventDate": self.event_date.text().strip(),
            "data_citation": data_citation,
            "observer": data_citation,  # compatibility with older temporary layers
            "source_ref": data_citation,
            "data_origin": data_origin,
            "data_curator": self.data_curator.text().strip(),
            "evidence": self.evidence.currentText(),
            "identifier": self.identifier.text().strip(),
            "catalog_no": self.identifier.text().strip(),
            "coordUncM": self.uncertainty.value(),
            "review": review_map.get(self.review.currentText(), "revisar"),
            "include": self.include.isChecked(),
            "notes": self.notes.text().strip(),
        }
        return values



class PointDistributionSettingsDialog(QDialog):
    """Form with shared fields for the IUCN Point Distribution CSV."""

    def __init__(self, parent=None, default_name: str = "", default_subspecies: str = "", defaults=None):
        super().__init__(parent)
        self.setWindowTitle("Final Point Distribution - IUCN attributes")
        self.resize(650, 540)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "These values will be applied to the Point Distribution CSV rows. "
            "The dec_lat and dec_long coordinates are filled automatically from the points used in the calculation. "
            "The file will follow exactly the column schema you provided."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        this_year = datetime.now().year
        self.sci_name = QLineEdit(default_name)

        self.presence = QComboBox()
        self.presence.addItem("1 - Extant", 1)
        self.presence.addItem("3 - Possibly Extant", 3)
        self.presence.addItem("4 - Possibly Extinct", 4)
        self.presence.addItem("5 - Extinct", 5)
        self.presence.addItem("6 - Presence Uncertain", 6)
        
        self.origin = QComboBox()
        self.origin.addItem("1 - Native", 1)
        self.origin.addItem("2 - Reintroduced", 2)
        self.origin.addItem("3 - Introduced", 3)
        self.origin.addItem("4 - Vagrant", 4)
        self.origin.addItem("5 - Origin Uncertain", 5)
        self.origin.addItem("6 - Assisted Colonisation", 6)
        
        self.seasonal = QComboBox()
        self.seasonal.addItem("1 - Resident", 1)
        self.seasonal.addItem("2 - Breeding Season", 2)
        self.seasonal.addItem("3 - Non-breeding Season", 3)
        self.seasonal.addItem("4 - Passage", 4)
        self.seasonal.addItem("5 - Seasonal Occurrence Uncertain", 5)

        self.compiler = QLineEdit()
        self.yrcompiled = QSpinBox()
        self.yrcompiled.setRange(1900, this_year + 1)
        self.yrcompiled.setValue(this_year)
        self.citation = QLineEdit()
        self.citation.setToolTip(IUCN_CITATION_HELP)
        self.spatialref = QLabel("WGS84 (EPSG:4326)")
        self.subspecies = QLineEdit(default_subspecies)
        self.requires_subspecies = bool(default_subspecies)
        self.subpop = QLineEdit()

        self.data_sens = QComboBox()
        self.data_sens.addItem("0 - Not sensitive", 0)
        self.data_sens.addItem("1 - Sensitive", 1)

        self.sens_comm = QLineEdit()
        self.source = QLineEdit("GBIF.org and reviewed user data")
        self.basisofrec = QLineEdit()
        self.dist_comm = QLineEdit()
        self.island = QLineEdit()
        self.tax_comm = QLineEdit()

        defaults = defaults or {}
        for field in ("presence", "origin", "seasonal", "data_sens"):
            control = getattr(self, field)
            index = control.findData(defaults.get(field))
            if index >= 0:
                control.setCurrentIndex(index)
        for field in ("compiler", "citation", "subpop", "sens_comm"):
            getattr(self, field).setText(str(defaults.get(field) or ""))
        if defaults.get("yrcompiled"):
            self.yrcompiled.setValue(defaults["yrcompiled"])

        form.addRow("sci_name *", self.sci_name)
        form.addRow("presence *", self.presence)
        form.addRow("origin *", self.origin)
        form.addRow("seasonal", self.seasonal)
        form.addRow("compiler *", self.compiler)
        form.addRow("yrcompiled *", self.yrcompiled)
        form.addRow("citation *", self.citation)
        form.addRow("spatialref * (automatic)", self.spatialref)
        form.addRow("subspecies * if applicable", self.subspecies)
        form.addRow("subpop * if applicable", self.subpop)
        form.addRow("data_sens", self.data_sens)
        form.addRow("sens_comm", self.sens_comm)
        layout.addLayout(form)
        optional = QWidget()
        optional_form = QFormLayout(optional)
        for field in ("source", "basisofrec", "dist_comm", "island", "tax_comm"):
            optional_form.addRow(field, getattr(self, field))
        optional.hide()
        optional_button = QPushButton("Optional record details")
        optional_button.setCheckable(True)
        optional_button.setToolTip("EN: Show recommended record details.\nES: Muestra los datos recomendados de los registros.")
        optional_button.toggled.connect(optional.setVisible)
        layout.addWidget(optional_button)
        layout.addWidget(optional)

        note = QLabel(
            "* Required or core fields for Point Distribution following the IUCN template. "
            "If data_sens = 1, fill in sens_comm. "
            "event_year is completed from the record date/year when available. "
            "catalog_no is filled with gbifID for GBIF records."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(_button_box_ok() | _button_box_cancel())
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        missing = []
        if self.requires_subspecies and not self.subspecies.text().strip():
            missing.append("subspecies")
        if not self.sci_name.text().strip():
            missing.append("sci_name")
        if not self.compiler.text().strip():
            missing.append("compiler")
        if not self.citation.text().strip():
            missing.append("citation")
        if self.data_sens.currentData() == 1 and not self.sens_comm.text().strip():
            missing.append("sens_comm because data_sens=1")
        if missing:
            QMessageBox.warning(self, "Point Distribution", "Missing fields: " + ", ".join(missing))
            return
        self.accept()

    def values(self) -> dict:
        return {
            "sci_name": self.sci_name.text().strip(),
            "presence": self.presence.currentData(),
            "origin": self.origin.currentData(),
            "seasonal": self.seasonal.currentData(),
            "compiler": self.compiler.text().strip(),
            "yrcompiled": self.yrcompiled.value(),
            "citation": self.citation.text().strip(),
            "subspecies": self.subspecies.text().strip(),
            "subpop": self.subpop.text().strip(),
            "data_sens": self.data_sens.currentData(),
            "sens_comm": self.sens_comm.text().strip(),
            "source": self.source.text().strip(),
            "basisofrec": self.basisofrec.text().strip(),
            "dist_comm": self.dist_comm.text().strip(),
            "island": self.island.text().strip(),
            "tax_comm": self.tax_comm.text().strip(),
        }


POINT_DISTRIBUTION_HELP = [
    ("sci_name", "Scientific name of the taxon. It must match the name used in the assessment."),
    ("presence", "IUCN presence code. Usually 1 = extant."),
    ("origin", "IUCN origin code. Usually 1 = native."),
    ("seasonal", "IUCN seasonal code. In plants this is usually 1 = resident, unless another case applies."),
    ("compiler", "Person or institution compiling the point file."),
    ("yrcompiled", "Year when the file is compiled or modified."),
    ("citation", "Overall credit for the distribution file. It should remain the same throughout the file."),
    ("dec_lat", "Decimal latitude of the point. The plugin fills it from the points used."),
    ("dec_long", "Decimal longitude of the point. The plugin fills it from the points used."),
    ("spatialref", "Coordinate reference system. Default is WGS84."),
    ("subspecies", "Infraspecific epithet if a subspecies or variety is being assessed."),
    ("subpop", "Subpopulation name, if applicable. Kept because it is part of the Point Distribution template."),
    ("data_sens", "0 = not sensitive; 1 = sensitive."),
    ("sens_comm", "Reason why the data are sensitive. Must be completed if data_sens = 1."),
    ("event_year", "Year of observation or collection, if available. The plugin tries to recover it from the record."),
    ("source", "Primary source of the point: GBIF, fieldwork, herbarium, report, publication, etc."),
    ("basisofrec", "Nature of the record, for example PreservedSpecimen or HumanObservation."),
    ("catalog_no", "Record identifier. For GBIF it is filled with gbifID when available."),
    ("dist_comm", "Distribution comment associated with the point."),
    ("island", "Island, if applicable."),
    ("tax_comm", "Taxonomic comment associated with the point."),
]


IUCN_CITATION_HELP = (
    "Citation / Cita\n"
    "EN: Enter the person or organisation providing the map data. Use the same credit throughout the file. "
    "Keep the primary data references in the assessment and cite an official GBIF download by its DOI.\n"
    "ES: Indica la persona o entidad que aporta los datos del mapa. Usa el mismo crédito en todo el archivo. "
    "Incluye las fuentes primarias en la evaluación y cita la descarga oficial de GBIF por su DOI.\n\n"
    "Reference / Referencia: IUCN. (2024). Standard attributes for spatial data, v1.20.\n"
    "https://nrl.iucnredlist.org/resources/mappingstandards"
)


class PointDistributionHelpDialog(QDialog):
    """Scrollable help for the exact Point Distribution CSV schema."""

    def __init__(self, parent=None, polygon=False):
        super().__init__(parent)
        self.setWindowTitle("AOO, EOO and Distribution field guide" if polygon else "Point Distribution field guide")
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        fields = ([(field, f"{definition} ({requirement})")
                   for field, definition, requirement in IUCN_POLYGON_FIELD_GUIDE]
                  if polygon else POINT_DISTRIBUTION_HELP)
        lines = [IUCN_CITATION_HELP, "", "IUCN attributes / Atributos UICN"]
        lines.extend(f"{field}: {definition}" for field, definition in fields)
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)

        buttons = QDialogButtonBox(_button_box_ok())
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)



COORDINATECLEANER_CRITERIOS_ES = [
    ("missing coordinates", "Records without usable latitude or longitude."),
    ("coordinates out of range", "Records with latitude outside -90/90 or longitude outside -180/180."),
    ("0,0 coordinates", "Records located exactly at point 0,0."),
    ("longitude equal to latitude", "Records where latitude and longitude are exactly the same."),
    ("GBIF issue: zero coordinate", "Records that GBIF already flags with a zero-coordinate issue."),
    ("GBIF issue: possible country centroid", "Records that GBIF already flags as a possible country centroid."),
    ("GBIF issue: invalid coordinate", "Records that GBIF flags as an invalid coordinate."),
    ("GBIF issue: coordinate out of range", "Records that GBIF flags as out of range."),
    ("GBIF headquarters", "Coordinates matching GBIF headquarters or the Copenhagen area."),
    ("capital coordinates", "Coordinates that match almost exactly some capital cities."),
    ("country centroids", "Coordinates that match almost exactly national centroids or very generic values."),
    ("institution coordinates", "Coordinates that match almost exactly some botanical institutions or museums."),
]

COORDINATECLEANER_REASON_TRANSLATION = {
    "coordenadas ausentes": "missing coordinates",
    "coordenadas fuera de rango": "coordinates out of range",
    "coordenadas 0,0": "coordinates 0,0",
    "longitud igual a latitud": "longitud igual a latitud",
    "GBIF issue ZERO_COORDINATE": "problema GBIF: coordenada cero",
    "GBIF issue COUNTRY_CENTROID": "GBIF issue: possible country centroid",
    "GBIF issue COORDINATE_INVALID": "GBIF issue: invalid coordinate",
    "GBIF issue COORDINATE_OUT_OF_RANGE": "problema GBIF: coordenada fuera de rango",
    "gbif_headquarters": "sede de GBIF",
    "capital_coordinates": "capital coordinates",
    "country_centroids": "country centroids",
    "institution_coordinates": "institution coordinates",
}

class AooEooDialog(QDialog):
    """Main non-modal plugin dialog."""

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.manual_layer = None
        self.manual_layer_id = None
        self.gbif_layer = None
        self.gbif_layer_id = None
        self.manual_tool = None
        self.previous_map_tool = None
        self.last_result = None
        self.point_distribution_layer = None
        self.gbif_doi_layer = None
        self.gbif_download_key = ""
        self.gbif_download_response = None
        self.calc_layers_list = None

        self.last_filter_removed = []
        self.setWindowTitle("IUCN Red List calculator")
        self.resize(1040, 780)
        self.setMinimumSize(900, 680)
        self._build_ui()
        # Both objects are constructed in _build_ui; failure to connect is a
        # genuine UI initialization error and must not be silently ignored.
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # The calculation layer list is not auto-populated from the whole project on startup,
        # because old project layers can otherwise appear as default data.
        # It is refreshed by user action or when the plugin itself creates/imports layers.

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = QVBoxLayout(self)
        intro = QLabel(
            "IUCN Red List spatial assessment support: retrieve GBIF occurrences, review source "
            "and coordinate quality, combine selected point layers, calculate AOO/EOO, and prepare "
            "editable distribution maps. Expert verification is required. Large downloads may slow QGIS."
        )
        intro.setToolTip(
            "EN: Check isolated records, coordinate precision and source attribution before using results.\n"
            "ES: Revisa los registros aislados, la precisión de las coordenadas y la procedencia "
            "de los datos antes de utilizar los resultados."
        )
        intro.setWordWrap(True)
        main.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.addTab(self._make_gbif_tab(), "1. GBIF and filters")
        self.tabs.addTab(self._make_data_tab(), "2. Layers and user points")
        self.tabs.addTab(self._make_calc_tab(), "3. Calculate AOO/EOO")
        self.tabs.addTab(self._make_report_tab(), "4. Final Point Distribution")
        self.geojson_tab = self._make_geojson_tab()
        self.tabs.addTab(self.geojson_tab, "5. GeoJSON export")
        self.tabs.addTab(self._make_gbif_citation_tab(), "6. GBIF citation / DOI")
        self.tabs.currentChanged.connect(self._refresh_geojson_if_visible)
        main.addWidget(self.tabs)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(110)
        self.log.setMaximumHeight(160)
        main.addWidget(self.log)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_button)
        main.addLayout(bottom)

    def _make_gbif_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_box = QGroupBox("GBIF search")
        form = QGridLayout(form_box)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        def etiqueta(texto: str, ayuda: str) -> QLabel:
            label = QLabel(texto)
            label.setToolTip(ayuda)
            return label

        self.scientific_name = QLineEdit()
        self.scientific_name.setPlaceholderText("E.g.: Genista sanabrensis; or full infraspecific name")
        # Al pulsar Enter desde el campo de nombre científico, resolver el taxonKey.
        # Evita que Qt active por defecto otro botón de la pestaña, como la tabla de criterios.
        self.scientific_name.returnPressed.connect(self.resolve_taxon)
        self.assess_infraspecific = QCheckBox("Evaluar como subespecie o variedad")
        self.assess_infraspecific.setChecked(False)
        self.infraspecific_epithet = QLineEdit()
        self.infraspecific_epithet.setPlaceholderText("Infraspecific epithet, e.g. brevifolia; optional")
        self.taxon_key = QLineEdit()
        self.taxon_key.setPlaceholderText("Optional; can be resolved from the name")
        self.country_code = QLineEdit()
        self.country_code.setMaxLength(2)
        self.country_code.setPlaceholderText("ES, PT, FR... optional")

        this_year = datetime.now().year
        self.year_min = QSpinBox()
        self.year_min.setRange(0, this_year + 1)
        self.year_min.setSpecialValueText("no minimum")
        self.year_min.setValue(0)
        self.year_max = QSpinBox()
        self.year_max.setRange(0, this_year + 1)
        self.year_max.setSpecialValueText("no maximum")
        self.year_max.setValue(0)
        self.scientific_name.setToolTip(
            "Scientific name to search in GBIF. It can be a species or a full infraspecific name. Example: Genista sanabrensis.\nES: Nombre científico que se buscará en GBIF. Puede ser especie o nombre infraespecífico completo. Ejemplo: Genista sanabrensis."
        )
        self.assess_infraspecific.setToolTip(
            "Check this when the assessment is for a subspecies or variety. The infraspecific epithet will later be used in the IUCN/SRedList outputs.\nES: Márcalo cuando la evaluación sea para una subespecie o variedad. El epíteto infraespecífico se usará después en las salidas IUCN/SRedList."
        )
        self.infraspecific_epithet.setToolTip(
            "Infraspecific epithet, without repeating the genus or species. Example: brevifolia.\nES: Epíteto infraespecífico, sin repetir el género ni la especie. Ejemplo: brevifolia."
        )
        self.taxon_key.setToolTip(
            "Numeric GBIF identifier for the taxon. Optional: you can resolve it from the scientific name using the Resolve taxonKey button.\nES: Identificador numérico de GBIF para el taxón. Es opcional: puedes resolverlo desde el nombre científico con el botón Resolver taxonKey."
        )
        self.country_code.setToolTip(
            "Two-letter ISO code to restrict the search by country. Examples: ES, PT, FR. Leave empty to avoid filtering by country.\nES: Código ISO de dos letras para limitar la búsqueda por país. Ejemplos: ES, PT, FR. Déjalo vacío para no filtrar por país."
        )
        self.year_min.setToolTip(
            "Minimum GBIF record year. Records earlier than this year will be removed from the download and documented in the removed-records table. Use 'no minimum' to disable this filter.\nES: Año mínimo del registro GBIF. Se eliminarán de la descarga los registros anteriores a este año y quedarán documentados en la tabla de registros eliminados. Usa 'sin mínimo' para no aplicar este filtro."
        )
        self.year_max.setToolTip(
            "Maximum GBIF record year. Records later than this year will be removed from the download and documented in the removed-records table. Use 'no maximum' to disable this filter.\nES: Año máximo del registro GBIF. Se eliminarán de la descarga los registros posteriores a este año y quedarán documentados en la tabla de registros eliminados. Usa 'sin máximo' para no aplicar este filtro."
        )
        self.exclude_geospatial_issues = QCheckBox("hasGeospatialIssue = false")
        self.exclude_geospatial_issues.setChecked(True)
        self.exclude_geospatial_issues.setToolTip(
            "When checked, GBIF returns only records without known general geospatial issues. It is recommended to keep it enabled.\nES: Cuando está marcado, GBIF devuelve solo registros sin incidencias geoespaciales generales conocidas. Es recomendable dejarlo activado."
        )
        self.has_coordinate = QCheckBox("hasCoordinate = true")
        self.has_coordinate.setChecked(True)
        self.has_coordinate.setEnabled(False)
        self.has_coordinate.setToolTip(
            "Requires records to have coordinates. This is necessary to calculate AOO, EOO and generate point outputs.\nES: Obliga a que los registros tengan coordenadas. Es necesario para calcular AOO, EOO y generar puntos."
        )

        self.occurrence_status = QComboBox()
        self.occurrence_status.addItem("Detected / Present", "PRESENT")
        self.occurrence_status.addItem("Not detected / Absent", "ABSENT")
        self.occurrence_status.addItem("All statuses", None)
        self.occurrence_status.setCurrentIndex(0)
        self.occurrence_status.setToolTip(
            "EN: Detected/Present selects positive occurrence records. GBIF now uses DETECTED "
            "as the updated term for PRESENT; both are accepted when calculating AOO/EOO. "
            "NOT_DETECTED and ABSENT are excluded from spatial presence calculations.\n"
            "ES: Detectado/Presente selecciona registros positivos de presencia. GBIF utiliza "
            "DETECTED como término actualizado de PRESENT; ambos se aceptan al calcular AOO/EOO. "
            "NOT_DETECTED y ABSENT quedan excluidos de los cálculos de presencia."
        )

        self.synonym_1 = QLineEdit()
        self.synonym_1.setPlaceholderText("Synonym 1, optional")
        self.synonym_2 = QLineEdit()
        self.synonym_2.setPlaceholderText("Synonym 2, optional")
        self.synonym_3 = QLineEdit()
        self.synonym_3.setPlaceholderText("Synonym 3, optional")
        self.synonym_4 = QLineEdit()
        self.synonym_4.setPlaceholderText("Synonym 4, optional")
        for syn_widget in [self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4]:
            syn_widget.setToolTip(
                "Alternative name or synonym that will also be queried in GBIF. Use it only when you want to include records published under another name.\nES: Nombre alternativo o sinónimo que también se consultará en GBIF. Úsalo solo cuando quieras sumar registros publicados bajo otro nombre."
            )

        self.coordinatecleaner_filter = QCheckBox("Apply automatic CoordinateCleaner-like filter")
        self.coordinatecleaner_filter.setChecked(True)
        cc_text = (
            "Enabled by default. Filter inspired by CoordinateCleaner (Zizka et al. 2019), as in SRedList: it can be disabled and flags records with coordinates matching capitals, country centroids, GBIF headquarters, some institutions, or equal longitude and latitude. In this plugin a conservative Python version is applied before creating the GBIF layer.\nES: Marcado por defecto. Filtro inspirado en CoordinateCleaner (Zizka et al. 2019), como en SRedList: puede desactivarse y señala registros con coordenadas coincidentes con capitales, centroides de país, la sede de GBIF, algunas instituciones o con longitud igual a latitud. En este plugin se aplica una versión Python conservadora antes de crear la capa GBIF."
        )
        self.coordinatecleaner_filter.setToolTip(cc_text)
        self.show_cc_criteria_button = QPushButton("View filter criteria")
        self.show_cc_criteria_button.setToolTip("Show the exact criteria and reasons applied by the CoordinateCleaner-like filter.\nES: Muestra los criterios exactos y los motivos aplicados por el filtro tipo CoordinateCleaner.")
        self.show_cc_criteria_button.setToolTip("Create a table listing the specific reasons applied by the CoordinateCleaner-like filter.\nES: Crea una tabla con los motivos concretos que puede aplicar el filtro tipo CoordinateCleaner.")
        self.show_cc_criteria_button.clicked.connect(self.create_coordinatecleaner_criteria_table)
        self.show_cc_criteria_button.setAutoDefault(False)
        self.show_cc_criteria_button.setDefault(False)

        self.gbif_uncertainty_filter = QCheckBox("Filter by coordinate uncertainty")
        self.gbif_uncertainty_filter.setChecked(False)
        self.gbif_uncertainty_filter.setToolTip(
            "Enable this filter if you want to remove GBIF records whose spatial uncertainty is larger than the given threshold. The threshold is interpreted in metres. Use the next checkbox to also exclude records without reported uncertainty.\nES: Activa este filtro si quieres retirar registros de GBIF cuya incertidumbre espacial sea mayor que el umbral indicado. El umbral se interpreta en metros. Marca la casilla siguiente para retirar también los registros sin incertidumbre declarada."
        )
        self.gbif_uncertainty_combo = QComboBox()
        self.gbif_uncertainty_combo.setEditable(True)
        self.gbif_uncertainty_combo.setToolTip(
            "Select a value from the drop-down list or type your own. Units are not mandatory: 7050 is interpreted as 7050 metres. You can also write 7050 m or 7.05 km.\nES: Selecciona un valor del desplegable o escribe uno propio. No es obligatorio escribir unidades: 7050 se interpreta como 7050 metros. También puedes escribir 7050 m o 7.05 km."
        )
        for label, value in [
            ("100 m", 100),
            ("250 m", 250),
            ("500 m", 500),
            ("1 km", 1000),
            ("2 km", 2000),
            ("5 km", 5000),
            ("10 km", 10000),
            ("No limit", None),
        ]:
            self.gbif_uncertainty_combo.addItem(label, value)
        self.gbif_uncertainty_combo.setCurrentText("1 km")

        form.addWidget(etiqueta("Scientific name", "Scientific name to be searched in GBIF. It can be a species or a full infraspecific name.\nES: Nombre del taxón que se buscará en GBIF. Puede ser especie o nombre infraespecífico completo."), 0, 0)
        form.addWidget(self.scientific_name, 0, 1)
        form.addWidget(etiqueta("taxonKey", "Numeric GBIF identifier. Optional and can be resolved from the scientific name.\nES: Identificador numérico de GBIF. Es opcional y puede resolverse desde el nombre científico."), 0, 2)
        form.addWidget(self.taxon_key, 0, 3)
        form.addWidget(self.assess_infraspecific, 1, 0)
        form.addWidget(self.infraspecific_epithet, 1, 1)
        form.addWidget(etiqueta("Country", "Two-letter ISO code to filter by country, for example ES. Leave empty to avoid filtering.\nES: Código ISO de dos letras para filtrar por país, por ejemplo ES. Déjalo vacío para no filtrar."), 1, 2)
        form.addWidget(self.country_code, 1, 3)
        form.addWidget(etiqueta("Minimum year", "Minimum GBIF record year. Earlier records will be removed and can be reviewed in the removed-records table.\nES: Año mínimo del registro GBIF. Los registros anteriores se retirarán y se podrán ver en la tabla de registros eliminados."), 2, 0)
        form.addWidget(self.year_min, 2, 1)
        form.addWidget(etiqueta("Maximum year", "Maximum GBIF record year. Later records will be removed and can be reviewed in the removed-records table.\nES: Año máximo del registro GBIF. Los registros posteriores se retirarán y se podrán ver en la tabla de registros eliminados."), 2, 2)
        form.addWidget(self.year_max, 2, 3)
        form.addWidget(etiqueta("Occurrence status", "PRESENT includes presence records. ABSENT should not be used to calculate AOO/EOO except under very specific review.\nES: PRESENT incluye registros de presencia. ABSENT no debe usarse para calcular AOO/EOO salvo revisión muy específica."), 3, 0)
        form.addWidget(self.occurrence_status, 3, 1)
        form.addWidget(self.has_coordinate, 4, 0)
        form.addWidget(self.exclude_geospatial_issues, 4, 1)
        form.addWidget(self.coordinatecleaner_filter, 5, 0, 1, 2)
        form.addWidget(self.show_cc_criteria_button, 5, 2, 1, 2)
        uncertainty_row = QHBoxLayout()
        uncertainty_row.addWidget(self.gbif_uncertainty_filter)
        uncertainty_row.addWidget(self.gbif_uncertainty_combo)
        self.gbif_require_uncertainty = QCheckBox("Exclude records without reported uncertainty")
        self.gbif_require_uncertainty.setToolTip(
            "EN: Exclude records without a usable uncertainty value. A reported value does not guarantee accuracy.\n"
            "ES: Excluye registros sin un valor de incertidumbre utilizable. Tener ese valor no garantiza que el punto sea exacto."
        )
        uncertainty_row.addWidget(self.gbif_require_uncertainty)
        uncertainty_row.addStretch(1)
        form.addLayout(uncertainty_row, 6, 0, 1, 4)
        form.addWidget(etiqueta("Optional synonyms", "Alternative names that will also be queried in GBIF. Use them to include records published under synonyms.\nES: Nombres alternativos que también se consultarán en GBIF. Úsalos para incluir registros publicados bajo sinónimos."), 7, 0)
        form.addWidget(self.synonym_1, 7, 1)
        form.addWidget(self.synonym_2, 7, 2)
        form.addWidget(self.synonym_3, 8, 1)
        form.addWidget(self.synonym_4, 8, 2)
        self.gbif_require_year = QCheckBox("Exclude records without a year")
        self.gbif_require_year.setToolTip(
            "EN: Exclude records without a usable GBIF occurrence year, even without a year range.\n"
            "ES: Excluye registros sin un año de observación utilizable, aunque no indiques un intervalo."
        )
        self.gbif_excluded_publishers = set()
        self.gbif_publisher_names = {}
        self.gbif_publishers_button = QPushButton("Exclude data publishers (0)")
        self.gbif_publishers_button.setToolTip(
            "EN: List publishers in the current search and tick those whose records you want to exclude.\n"
            "ES: Lista los publicadores de la búsqueda actual. Marca aquellos cuyos registros quieras excluir."
        )
        self.gbif_publishers_button.clicked.connect(self._choose_excluded_publishers)
        form.addWidget(self.gbif_require_year, 9, 0, 1, 2)
        form.addWidget(self.gbif_publishers_button, 9, 2, 1, 2)
        self.gbif_excluded_collections = {}
        self.gbif_collections_button = QPushButton("Exclude collections (0)")
        self.gbif_collections_button.setToolTip(
            "EN: List collections in this search and tick those to exclude. Collection codes are shown with their source.\n"
            "ES: Lista las colecciones de la búsqueda. Marca las que quieras excluir. Los códigos se muestran con su procedencia."
        )
        self.gbif_collections_button.clicked.connect(self._choose_excluded_collections)
        form.addWidget(self.gbif_collections_button, 10, 2, 1, 2)
        layout.addWidget(form_box)

        filters = QHBoxLayout()
        self.basis_list = self._make_check_list(BASIS_OPTIONS)
        self.basis_list.setToolTip(
            "Record type in GBIF. For plants, HUMAN_OBSERVATION and PRESERVED_SPECIMEN are often useful. MACHINE_OBSERVATION is unchecked by default.\nES: Tipo de registro en GBIF. Para plantas suelen ser útiles HUMAN_OBSERVATION y PRESERVED_SPECIMEN. MACHINE_OBSERVATION queda desmarcado por defecto."
        )
        basis_box = QGroupBox("basisOfRecord")
        basis_box.setToolTip(
            "Nature of the record: human observation, preserved specimen, machine observation, sample, etc.\nES: Naturaleza del registro: observación humana, pliego conservado, observación de máquina, muestra, etc."
        )
        basis_layout = QVBoxLayout(basis_box)
        basis_layout.addWidget(self.basis_list)
        filters.addWidget(basis_box)

        self.establishment_list = self._make_check_list(ESTABLISHMENT_OPTIONS)
        self.establishment_list.setToolTip(
            "Origin or establishment means of the record according to GBIF: native, introduced, reintroduced, uncertain, etc.\nES: Origen o forma de establecimiento del registro según GBIF: nativo, introducido, reintroducido, incierto, etc."
        )
        est_box = QGroupBox("establishmentMeans")
        est_box.setToolTip(
            "Allows filtering by origin of the taxon. For native-distribution assessments, this is usually reviewed carefully.\nES: Permite filtrar por origen del taxón. Para evaluaciones de distribución nativa, suele revisarse con cuidado."
        )
        est_layout = QVBoxLayout(est_box)
        est_layout.addWidget(self.establishment_list)
        self.filter_establishment = QCheckBox("Apply this filter")
        self.filter_establishment.setChecked(False)
        self.filter_establishment.setToolTip(
            "If unchecked, the selected establishmentMeans values are not used to filter. Check it only if you want to restrict records by origin.\nES: Si no está marcado, los valores seleccionados de establishmentMeans no se usan para filtrar. Márcalo solo si quieres restringir los registros por origen."
        )
        est_layout.addWidget(self.filter_establishment)
        filters.addWidget(est_box)
        layout.addLayout(filters)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(6)
        self.resolve_button = QPushButton("Resolve taxonKey")
        self.resolve_button.setToolTip("Resolve the GBIF taxonKey from the scientific name.\nES: Resuelve el taxonKey de GBIF a partir del nombre científico indicado.")
        self.resolve_button.setToolTip("Resolve the GBIF taxonKey from the scientific name.\nES: Resuelve el taxonKey de GBIF a partir del nombre científico.")
        self.resolve_button.clicked.connect(self.resolve_taxon)
        self.preview_button = QPushButton("Preview GBIF counts")
        self.preview_button.setToolTip(
            "EN: Count records after applying the same GBIF and local filters as the download. "
            "This reads the matching records without adding a layer.\n"
            "ES: Cuenta los registros con los mismos filtros de GBIF y locales que la descarga. "
            "Consulta los registros sin crear una capa."
        )
        self.preview_button.clicked.connect(self.preview_facets)
        self.preview_gbif_records_button = QPushButton("Preview GBIF records")
        self.preview_gbif_records_button.setToolTip(
            "EN: Show the filtered points on the map and open their attribute table as a temporary preview.\n"
            "ES: Muestra los puntos filtrados en el mapa y abre su tabla de atributos como vista previa temporal."
        )
        self.preview_gbif_records_button.clicked.connect(self.preview_gbif_records)
        self.gbif_preview_id = None
        self.download_button = QPushButton("Download GBIF occurrences")
        self.download_button.setToolTip("Download records from GBIF using the filters set in this tab.\nES: Descarga registros de GBIF usando los filtros indicados en esta pestaña.")
        self.download_button.clicked.connect(self.download_gbif)
        self.reset_gbif_button = QPushButton("Reset filters")
        self.reset_gbif_button.setToolTip(
            "EN: Restore the GBIF filters to their defaults and keep the taxon and synonyms.\n"
            "ES: Restablece los filtros de GBIF y conserva el taxón y los sinónimos."
        )
        self.reset_gbif_button.clicked.connect(self.reset_gbif_filters)
        self.clear_gbif_button = QPushButton("Clear GBIF tab")
        self.clear_gbif_button.setToolTip(
            "EN: Clear the search fields, preview and visible log, and restore the default filters.\n"
            "ES: Borra los campos de búsqueda, la vista previa y el registro visible, y restablece los filtros."
        )
        self.clear_gbif_button.clicked.connect(self.reset_gbif_tab)
        self.show_filtered_button = QPushButton("View removed records")
        self.show_filtered_button.setToolTip("Create a table with the records removed by the filters applied in the last GBIF download.\nES: Crea una tabla con los registros retirados por los filtros aplicados en la última descarga GBIF.")
        self.show_filtered_button.clicked.connect(self.create_filtered_records_table)
        self.stop_gbif_button = QPushButton("Stop GBIF")
        self.stop_gbif_button.setEnabled(False)
        self.stop_gbif_button.setToolTip(
            "EN: Stop the count, record preview or download after the current GBIF request finishes. Partial results are discarded.\n"
            "ES: Detiene el conteo, la vista previa de registros o la descarga al terminar la consulta en curso. Se descartan los resultados parciales."
        )
        self.stop_gbif_button.clicked.connect(self._stop_gbif_query)
        self.gbif_query_cancelled = False
        for _boton_gbif in [
            self.resolve_button,
            self.preview_button,
            self.preview_gbif_records_button,
            self.download_button,
            self.reset_gbif_button,
            self.clear_gbif_button,
            self.show_filtered_button,
            self.stop_gbif_button,
        ]:
            _boton_gbif.setAutoDefault(False)
            _boton_gbif.setDefault(False)
        self.resolve_button.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        self.preview_button.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        self.download_button.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        self.show_filtered_button.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        self.reset_gbif_button.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        buttons.addWidget(self.resolve_button, 0, 0)
        buttons.addWidget(self.preview_gbif_records_button, 0, 2)
        buttons.addWidget(self.download_button, 0, 3)
        buttons.addWidget(self.preview_button, 0, 1)
        buttons.addWidget(self.reset_gbif_button, 1, 0)
        buttons.addWidget(self.clear_gbif_button, 1, 1)
        buttons.addWidget(self.show_filtered_button, 1, 2)
        buttons.addWidget(self.stop_gbif_button, 1, 3)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return tab

    def _make_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.layer_combo = None  # compatibilidad interna: la selección de capas se hace en la pestaña 3

        manual_box = QGroupBox("User-added points")
        manual_layout = QVBoxLayout(manual_box)
        self.manual_status = QLabel("Manual points layer will be created automatically when you add your first point.")
        manual_layout.addWidget(self.manual_status)
        manual_buttons = QGridLayout()
        self.activate_manual_button = QPushButton("Add point by clicking on the map")
        self.activate_manual_button.setToolTip("Activate a map tool to add user points by clicking on the map canvas.\nES: Activa una herramienta de mapa para añadir puntos propios haciendo clic en el mapa.")
        self.activate_manual_button.clicked.connect(self.activate_manual_point_tool)
        self.add_manual_coordinates_button = QPushButton("Add point by entering coordinates")
        self.add_manual_coordinates_button.setToolTip("Open a form to add a point by decimal coordinates.\nES: Abre un formulario para añadir un punto mediante coordenadas decimales.")
        self.add_manual_coordinates_button.clicked.connect(self.add_manual_point_by_coordinates)
        self.stop_manual_button = QPushButton("Stop adding points")
        self.stop_manual_button.setToolTip("Stop the current point-adding mode.\nES: Detiene el modo actual de adición de puntos.")
        self.stop_manual_button.clicked.connect(self.stop_manual_point_tool)
        self.import_csv_button = QPushButton("Import my points from CSV")
        self.import_csv_button.setToolTip("Import CSV points as a new, independent layer. Each imported file remains separate from points added manually.\nES: Importa el CSV en una capa nueva e independiente, separada de los puntos introducidos manualmente.")
        self.import_csv_button.clicked.connect(self.import_manual_points_csv)
        self.import_shapefile_button = QPushButton("Import points from shapefile")
        self.import_shapefile_button.setToolTip("Load a point shapefile into the QGIS project and mark it so it can be used directly in the tab 3 calculation. Its original attribute table is preserved.\nES: Carga un shapefile de puntos en el proyecto de QGIS y lo marca para poder usarlo directamente en el cálculo de la pestaña 3. Se conserva su tabla de atributos original.")
        self.import_shapefile_button.clicked.connect(self.import_point_shapefile)
        self.save_csv_template_button = QPushButton("Save occurrence CSV template")
        self.save_csv_template_button.setToolTip("Save a base CSV template compatible with the plugin.\nES: Guarda una plantilla base CSV compatible con el plugin.")
        self.save_csv_template_button.clicked.connect(self.save_manual_csv_template)
        manual_buttons.addWidget(self.activate_manual_button, 0, 0)
        manual_buttons.addWidget(self.add_manual_coordinates_button, 0, 1)
        manual_buttons.addWidget(self.import_csv_button, 1, 0)
        manual_buttons.addWidget(self.import_shapefile_button, 1, 1)
        manual_buttons.addWidget(self.save_csv_template_button, 2, 0, 1, 2)
        manual_buttons.addWidget(self.stop_manual_button, 3, 0, 1, 2)
        manual_layout.addLayout(manual_buttons)
        hint = QLabel(
            'A manual layer is created automatically when your first point is saved. Points added by clicking or entering coordinates use that layer; each imported CSV becomes a new independent layer. You can also import a point shapefile as an independent QGIS layer, preserving its original attribute table. If you need to delete or correct points, edit the layer directly in QGIS and then calculate from the checked layers in tab 3. Manual points must be marked for use; CSV records without an explicit include/review value are accepted by default, while explicit exclusions are preserved. CSV import accepts latitude as decimalLatitude, latitude, lat or dec_lat, and longitude as decimalLongitude, longitude, lon, lng, dec_lon, dec_long or long.'
        )
        hint.setWordWrap(True)
        manual_layout.addWidget(hint)
        layout.addWidget(manual_box)
        layout.addStretch(1)
        return tab

    def _make_calc_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except AttributeError:
            pass
        content = QWidget()
        layout = QVBoxLayout(content)

        layers_box = QGroupBox("Layers to use in the calculation")
        layers_layout = QVBoxLayout(layers_box)
        layers_hint = QLabel(
            'Check one or more point layers in the project. The calculation will use only the checked layers. This allows AOO/EOO to be calculated from GBIF, imported CSV, user points, any point layer loaded in QGIS, or several combined layers.'
        )
        layers_hint.setWordWrap(True)
        layers_layout.addWidget(layers_hint)
        self.calc_layers_list = QListWidget()
        self.calc_layers_list.setMinimumHeight(150)
        # QListWidget supports this selection mode in supported Qt versions.
        self.calc_layers_list.setSelectionMode(
            getattr(QAbstractItemView, "MultiSelection", None)
            or QAbstractItemView.SelectionMode.MultiSelection
        )
        layers_layout.addWidget(self.calc_layers_list)
        self.calc_selection_summary = QLabel("Selected for calculation / Capas seleccionadas: none / ninguna")
        self.calc_selection_summary.setWordWrap(True)
        layers_layout.addWidget(self.calc_selection_summary)
        self.calc_layers_list.itemChanged.connect(self._update_calc_selection_summary)
        layer_buttons = QGridLayout()
        self.refresh_calc_layers_button = QPushButton("Refresh layer list")
        self.refresh_calc_layers_button.setToolTip("Refresh the list of point layers available in the current QGIS project.\nES: Actualiza la lista de capas de puntos disponibles en el proyecto actual de QGIS.")
        self.refresh_calc_layers_button.clicked.connect(lambda: self.refresh_calc_layers(apply_defaults=False))
        self.check_current_layer_button = QPushButton("Check active layer")
        self.check_current_layer_button.setToolTip("Check the currently active point layer.\nES: Marca la capa de puntos activa en este momento.")
        self.check_current_layer_button.clicked.connect(self.check_current_calc_layer)
        self.check_all_layers_button = QPushButton("Check all")
        self.check_all_layers_button.setToolTip("Check all available point layers.\nES: Marca todas las capas de puntos disponibles.")
        self.check_all_layers_button.clicked.connect(self.check_all_calc_layers)
        self.uncheck_all_layers_button = QPushButton("Uncheck all")
        self.uncheck_all_layers_button.setToolTip("Uncheck all available point layers.\nES: Desmarca todas las capas de puntos disponibles.")
        self.uncheck_all_layers_button.clicked.connect(self.uncheck_all_calc_layers)
        layer_buttons.addWidget(self.refresh_calc_layers_button, 0, 0)
        layer_buttons.addWidget(self.check_current_layer_button, 0, 1)
        layer_buttons.addWidget(self.check_all_layers_button, 1, 0)
        layer_buttons.addWidget(self.uncheck_all_layers_button, 1, 1)
        layers_layout.addLayout(layer_buttons)
        layout.addWidget(layers_box)
        # The list is intentionally left empty on dialog opening/tab creation.
        # This avoids showing old project layers as if they were default input data.
        # Users can press "Refresh layer list", or the plugin will add layers here
        # after a new GBIF download/import/manual layer is created in the current session.

        opts = QGroupBox("Calculation parameters")
        form = QFormLayout(opts)
        _set_form_expanding_fields(form)
        self.analysis_crs = QComboBox()
        self.analysis_crs.setEditable(True)
        self.analysis_crs.setMinimumWidth(320)
        self.analysis_crs.setSizePolicy(SizePolicy.Expanding, SizePolicy.Fixed)
        self.analysis_crs.setToolTip(
            "Choose a projected CRS with metre units appropriate to the species range. "
            "Equal-area projections are recommended for area comparisons. "
            "You can also enter an EPSG code manually or use 'Choose CRS...' to browse QGIS systems. "
            "GBIF/SRedList Point Distribution exports remain EPSG:4326.\n"
            "ES: Elige un CRS proyectado en metros adecuado a la distribución de la especie. "
            "Para comparar superficies, se recomiendan proyecciones equivalentes. "
            "También puedes escribir un código EPSG o utilizar 'Elegir CRS...' para buscarlo en QGIS. "
            "Las exportaciones Point Distribution permanecen en EPSG:4326."
        )
        for label, epsg in [
            ("EUROPE — ETRS89 / LAEA Europe (equal-area) — EPSG:3035", "EPSG:3035"),
            ("Europe — ETRS89 / UTM zone 29N — EPSG:25829", "EPSG:25829"),
            ("Europe — ETRS89 / UTM zone 30N — EPSG:25830", "EPSG:25830"),
            ("Europe — ETRS89 / UTM zone 31N — EPSG:25831", "EPSG:25831"),
            ("Europe (legacy) — ED50 / UTM zone 29N — EPSG:23029", "EPSG:23029"),
            ("Europe (legacy) — ED50 / UTM zone 30N — EPSG:23030", "EPSG:23030"),
            ("Europe (legacy) — ED50 / UTM zone 31N — EPSG:23031", "EPSG:23031"),
            ("Europe — WGS 84 / UTM zone 29N — EPSG:32629", "EPSG:32629"),
            ("Europe — WGS 84 / UTM zone 30N — EPSG:32630", "EPSG:32630"),
            ("Europe — WGS 84 / UTM zone 31N — EPSG:32631", "EPSG:32631"),
            ("GLOBAL — WGS 84 / NSIDC EASE-Grid 2.0 Global (equal-area) — EPSG:6933", "EPSG:6933"),
            ("Global — WGS 84 / Equal Earth (equal-area) — EPSG:8857", "EPSG:8857"),
            ("AUSTRALIA — GDA2020 / Australian Albers (equal-area) — EPSG:9473", "EPSG:9473"),
            ("Australia (legacy) — GDA94 / Australian Albers (equal-area) — EPSG:3577", "EPSG:3577"),
            ("NEW ZEALAND — NZGD2000 / NZTM2000 — EPSG:2193", "EPSG:2193"),
            ("SOUTH POLAR REGION — WGS 84 / NSIDC EASE-Grid 2.0 South (equal-area) — EPSG:6932", "EPSG:6932"),
            ("Southern hemisphere — WGS 84 / UTM zone 55S — EPSG:32755", "EPSG:32755"),
        ]:
            self.analysis_crs.addItem(label, epsg)
        self.analysis_crs.setCurrentIndex(0)
        self.choose_analysis_crs_button = QPushButton("Choose CRS...")
        self.choose_analysis_crs_button.setMinimumWidth(120)
        self.choose_analysis_crs_button.setSizePolicy(SizePolicy.Fixed, SizePolicy.Fixed)
        self.choose_analysis_crs_button.setToolTip(
            "Open the QGIS CRS browser / Abrir el selector de CRS de QGIS"
        )
        self.choose_analysis_crs_button.clicked.connect(self._choose_analysis_crs)
        crs_row = QWidget()
        crs_row_layout = QHBoxLayout(crs_row)
        crs_row_layout.setContentsMargins(0, 0, 0, 0)
        crs_row_layout.addWidget(self.analysis_crs)
        crs_row_layout.addWidget(self.choose_analysis_crs_button)
        crs_row_layout.addStretch()
        self.cell_size = QDoubleSpinBox()
        self.cell_size.setRange(1, 100000)
        self.cell_size.setValue(2000)
        self.cell_size.setSuffix(" m")
        self.cell_size.setDecimals(0)
        self.cell_size.setMaximumWidth(160)
        self.cell_size.setToolTip(
            "IUCN standard AOO reference grid: 2 × 2 km = 2000 m. "
            "A different cell size requires explicit confirmation when calculating. / "
            "Cuadrícula AOO de referencia UICN: 2 × 2 km = 2000 m."
        )
        self.reset_cell_size_button = QPushButton("Reset to IUCN 2 km")
        self.reset_cell_size_button.clicked.connect(lambda: self.cell_size.setValue(2000))
        cell_size_row = QWidget()
        cell_size_layout = QHBoxLayout(cell_size_row)
        cell_size_layout.setContentsMargins(0, 0, 0, 0)
        cell_size_layout.addWidget(self.cell_size)
        cell_size_layout.addWidget(self.reset_cell_size_button)
        cell_size_layout.addStretch()

        self.include_pending = QCheckBox("Also use points marked as ‘review before use’")
        self.include_pending.setChecked(False)
        self.deduplicate = QCheckBox("Remove exact spatial duplicates")
        self.deduplicate.setChecked(True)
        self.use_uncertainty_filter = QCheckBox("Maximum coordinate uncertainty for AOO/EOO")
        self.use_uncertainty_filter.setChecked(False)
        self.use_uncertainty_filter.setToolTip(
            "EN: If enabled, excludes points above this uncertainty threshold from ALL checked layers. "
            "Records without declared uncertainty are retained for expert review.\n"
            "ES: Si se activa, excluye puntos cuya incertidumbre supere el umbral de TODAS las capas marcadas. "
            "Los registros sin incertidumbre declarada se mantienen para revisión experta."
        )
        self.max_uncertainty = QDoubleSpinBox()
        self.max_uncertainty.setRange(0, 1_000_000)
        self.max_uncertainty.setValue(1000)
        self.max_uncertainty.setSuffix(" m")
        self.max_uncertainty.setDecimals(0)
        self.max_uncertainty.setMaximumWidth(160)

        form.addRow("Analysis CRS for AOO/EOO / CRS de análisis para AOO/EOO", crs_row)
        form.addRow("AOO cell size (IUCN reference: 2000 m)", cell_size_row)
        form.addRow("Points under review", self.include_pending)
        form.addRow("Duplicates", self.deduplicate)
        self.max_uncertainty.setToolTip(
            "EN: Maximum coordinate uncertainty in metres for all selected point layers.\n"
            "ES: Incertidumbre máxima, en metros, para todas las capas de puntos seleccionadas."
        )
        form.addRow(self.use_uncertainty_filter, self.max_uncertainty)
        layout.addWidget(opts)

        iucn_box = QGroupBox("IUCN attributes for AOO, EOO and Distribution")
        iucn_form = QFormLayout(iucn_box)
        _set_form_expanding_fields(iucn_form)
        this_year = datetime.now().year
        self.iucn_presence = QComboBox()
        self.iucn_presence.addItem("1 - Extant", 1)
        self.iucn_presence.addItem("3 - Possibly Extant", 3)
        self.iucn_presence.addItem("4 - Possibly Extinct", 4)
        self.iucn_presence.addItem("5 - Extinct", 5)
        self.iucn_presence.addItem("6 - Presence Uncertain", 6)
        self.iucn_presence.addItem("7 - Expected Additional Range", 7)
        self.iucn_presence.setMaximumWidth(360)

        self.iucn_origin = QComboBox()
        self.iucn_origin.addItem("1 - Native", 1)
        self.iucn_origin.addItem("2 - Reintroduced", 2)
        self.iucn_origin.addItem("3 - Introduced", 3)
        self.iucn_origin.addItem("4 - Vagrant", 4)
        self.iucn_origin.addItem("5 - Origin Uncertain", 5)
        self.iucn_origin.addItem("6 - Assisted Colonisation", 6)
        self.iucn_origin.addItem("7 - Mixed origin", 7)
        self.iucn_origin.setMaximumWidth(360)

        self.iucn_seasonal = QComboBox()
        self.iucn_seasonal.addItem("1 - Resident", 1)
        self.iucn_seasonal.addItem("2 - Breeding Season", 2)
        self.iucn_seasonal.addItem("3 - Non-breeding Season", 3)
        self.iucn_seasonal.addItem("4 - Passage", 4)
        self.iucn_seasonal.addItem("5 - Seasonal Occurrence Uncertain", 5)
        self.iucn_seasonal.setMaximumWidth(360)

        self.iucn_compiler = QLineEdit()
        self.iucn_compiler.setMaximumWidth(420)
        self.iucn_yrcompiled = QSpinBox()
        self.iucn_yrcompiled.setRange(1900, this_year + 1)
        self.iucn_yrcompiled.setValue(this_year)
        self.iucn_yrcompiled.setMaximumWidth(120)
        self.iucn_citation = QLineEdit()
        self.iucn_citation.setToolTip(IUCN_CITATION_HELP)
        self.iucn_citation.setMaximumWidth(520)
        self.iucn_subpop = QLineEdit()
        self.iucn_subspecies = QLineEdit()
        self.iucn_subspecies.setMaximumWidth(320)
        self.iucn_data_sens = QComboBox()
        self.iucn_data_sens.addItem("0 - Not sensitive", 0)
        self.iucn_data_sens.addItem("1 - Sensitive", 1)
        self.iucn_data_sens.setMaximumWidth(200)
        self.iucn_sens_comm = QLineEdit()
        self.iucn_sens_comm.setMaximumWidth(520)

        self.iucn_sci_name = QLineEdit()
        self.iucn_sci_name.setPlaceholderText("Defaults to the scientific name in the GBIF tab")
        iucn_form.addRow("sci_name *", self.iucn_sci_name)
        iucn_form.addRow("presence *", self.iucn_presence)
        iucn_form.addRow("origin *", self.iucn_origin)
        iucn_form.addRow("seasonal * if applicable", self.iucn_seasonal)
        iucn_form.addRow("compiler *", self.iucn_compiler)
        iucn_form.addRow("yrcompiled *", self.iucn_yrcompiled)
        iucn_form.addRow("citation *", self.iucn_citation)
        iucn_form.addRow("subspecies if applicable", self.iucn_subspecies)
        iucn_form.addRow("subpop if applicable", self.iucn_subpop)
        iucn_form.addRow("data_sens if sensitive", self.iucn_data_sens)
        iucn_form.addRow("sens_comm * if data_sens=1", self.iucn_sens_comm)
        note = QLabel(
            'Required and conditional attributes for AOO, EOO and Distribution.'
        )
        note.setWordWrap(True)
        iucn_form.addRow("Note", note)
        self.iucn_fields_help_button = QPushButton("AOO, EOO and Distribution field guide")
        self.iucn_fields_help_button.setToolTip("EN: Read the required IUCN polygon fields and citation guidance.\nES: Consulta los campos obligatorios de polígonos UICN y cómo citarlos.")
        self.iucn_fields_help_button.clicked.connect(self.create_iucn_polygon_field_guide)
        iucn_form.addRow("Help", self.iucn_fields_help_button)
        layout.addWidget(iucn_box)

        threshold_note = QLabel(
            'The report adds an indicative category according to the spatial AOO and EOO thresholds of IUCN Criterion B. It does not replace a formal Red List assessment, because the plugin does not evaluate the additional subcriteria.'
        )
        threshold_note.setWordWrap(True)
        layout.addWidget(threshold_note)

        buttons = QHBoxLayout()
        self.calc_button = QPushButton("Calculate AOO/EOO")
        self.calc_button.setToolTip("Run the AOO/EOO calculation using only the checked point layers.\nES: Ejecuta el cálculo AOO/EOO usando solo las capas de puntos marcadas.")
        self.calc_button.clicked.connect(self.calculate)
        buttons.addStretch(1)
        buttons.addWidget(self.calc_button)
        self.remove_aoo_eoo_button = QPushButton("Remove AOO/EOO results")
        self.remove_aoo_eoo_button.setToolTip(
            "EN: Remove generated AOO/EOO polygons, report tables and legacy used-point layers from the project.\n"
            "ES: Retira del proyecto los polígonos AOO y EOO, los informes y las capas de puntos usados de cálculos anteriores."
        )
        self.remove_aoo_eoo_button.clicked.connect(self.remove_generated_aoo_eoo)
        buttons.addWidget(self.remove_aoo_eoo_button)
        layout.addLayout(buttons)

        self.range_preview_id = None
        range_box = QGroupBox("Distribution range polygon (expert-reviewed)")
        range_form = QFormLayout(range_box)
        _set_form_expanding_fields(range_form)
        range_intro = QLabel(
            "Optional cartographic range derived from the occurrence points used in the last AOO/EOO calculation. "
            "This is NOT AOO, EOO, or confirmed occupied habitat. Check boundaries and unsuitable habitat before use."
        )
        range_intro.setWordWrap(True)
        range_form.addRow(range_intro)
        self.range_mode = QComboBox()
        self.range_mode.addItem("Select a disjunct-group treatment...", None)
        self.range_mode.addItem("Keep non-overlapping patches separate", "separate")
        self.range_mode.addItem("Connect disjunct groups into one polygon", "merge")
        self.range_mode.setCurrentIndex(self.range_mode.findData("merge"))
        self.range_mode.setToolTip(
            "EN: Choose whether geographically disjunct occurrence groups remain separate or are connected into one envelope. "
            "Overlapping footprints are dissolved in separate mode.\nES: Decide si los núcleos disyuntos se mantienen separados o se conectan "
            "en una envolvente. En modo separado se disuelven las manchas que se solapan."
        )
        range_form.addRow("Disjunct groups", self.range_mode)
        self.range_group_distance = self._range_distance_combo(25000, 1000000, grouping=True)
        self.range_group_distance.setEnabled(False)
        self.range_group_distance.setToolTip(
            "EN: In separate mode, connect records into the same group only if a chain of points "
            "has pairwise distances at most this threshold (in the selected projected CRS). "
            "The researcher must set an ecologically suitable value; increasing it reduces very small separate patches.\n"
            "ES: En modo separado, agrupa los registros conectados por distancias entre puntos "
            "iguales o inferiores a este umbral. El investigador debe elegir un valor adecuado."
        )
        range_form.addRow("Grouping distance (separate mode)", self.range_group_distance)
        self.range_mode.currentIndexChanged.connect(
            lambda _index: self.range_group_distance.setEnabled(self.range_mode.currentData() == "separate")
        )
        self.range_concavity = QDoubleSpinBox()
        self.range_concavity.setRange(0.05, 1)
        self.range_concavity.setSingleStep(0.05)
        self.range_concavity.setDecimals(2)
        self.range_concavity.setValue(0.80)
        self.range_concavity.setToolTip(
            "EN: Lower values allow deeper indentations between points. Values near 1 give a wider, more convex outline.\nES: Los valores bajos permiten entrantes entre puntos. Cerca de 1, el contorno es más amplio y convexo."
        )
        range_form.addRow("Concavity (0.05–1.00)", self.range_concavity)
        self.range_smoothing = QSpinBox()
        self.range_smoothing.setRange(0, 5)
        self.range_smoothing.setValue(1)
        self.range_smoothing.setToolTip(
            "EN: Smooth the final outline after buffering. Higher values round the outline more. "
            "The plugin tries a gentler adjustment if needed to retain records and keep merged ranges connected.\n"
            "ES: Suaviza el contorno final después de aplicar el búfer. Más iteraciones redondean más el borde. "
            "Si hace falta, se reduce la intensidad para conservar los registros y la continuidad del rango fusionado."
        )
        range_form.addRow("Smoothing iterations", self.range_smoothing)
        self.range_round_tips = QCheckBox("Round sharp tips")
        self.range_round_tips.setToolTip(
            "EN: Detect and round sharp tips in the final outline while retaining all records.\n"
            "ES: Detecta y redondea las puntas pronunciadas del contorno final conservando todos los registros."
        )
        self.range_tip_radius = self._range_distance_combo(2000, 100000)
        self.range_tip_radius.setEnabled(False)
        self.range_tip_radius.setToolTip(
            "EN: Local rounding radius in metres. If the tip cannot be safely trimmed, it may expand locally.\n"
            "ES: Radio local en metros. Si la punta no se puede recortar con seguridad, puede ampliarse en esa zona."
        )
        self.range_round_tips.toggled.connect(self.range_tip_radius.setEnabled)
        range_form.addRow(self.range_round_tips)
        range_form.addRow("Tip rounding radius", self.range_tip_radius)
        self.range_buffer = self._range_distance_combo(2000, 100000)
        self.range_buffer.setToolTip(
            "EN: Distance added around the outline in metres. Increasing it expands the whole range.\nES: Distancia en metros que se añade alrededor del borde. Aumentarla amplía toda la mancha."
        )
        range_form.addRow("Boundary buffer", self.range_buffer)
        self.range_generate_button = QPushButton("Generate distribution range polygon")
        self.range_generate_button.setToolTip(
            "EN: Generate editable QGIS polygon layer(s) from the LAST completed calculation. "
            "Re-run AOO/EOO after changing input points. Review before submitting to IUCN.\n"
            "ES: Genera capas poligonales editables con los puntos del ÚLTIMO cálculo. "
            "Recalcula AOO/EOO si cambias los registros. Revisa el mapa antes de enviarlo a la UICN."
        )
        self.range_preview_button = QPushButton("Preview distribution range")
        self.range_preview_button.setToolTip(
            "EN: Show the range with the current settings as a temporary map layer. A new preview replaces the previous one.\n"
            "ES: Muestra el rango con los ajustes actuales en una capa temporal. Cada vista previa sustituye a la anterior."
        )
        self.range_preview_button.clicked.connect(lambda: self.generate_distribution_range(preview=True))
        self.range_remove_preview_button = QPushButton("Remove preview")
        self.range_remove_preview_button.setToolTip(
            "EN: Remove the preview layer from the map.\nES: Quita del mapa la capa de vista previa."
        )
        self.range_remove_preview_button.clicked.connect(self._remove_range_preview)
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.range_preview_button)
        preview_row.addWidget(self.range_remove_preview_button)
        self.reset_range_button = QPushButton("Reset range parameters")
        self.reset_range_button.setToolTip(
            "EN: Restore the initial range settings, including concavity 0.80.\n"
            "ES: Restablece los ajustes iniciales del rango, incluida la concavidad de 0,80."
        )
        self.reset_range_button.clicked.connect(self.reset_range_parameters)
        preview_row.addWidget(self.reset_range_button)
        range_form.addRow(preview_row)
        self.range_generate_button.clicked.connect(lambda: self.generate_distribution_range())
        range_form.addRow(self.range_generate_button)
        for control in (
            self.range_mode, self.range_group_distance, self.range_concavity,
            self.range_smoothing, self.range_tip_radius, self.range_buffer,
        ):
            range_form.labelForField(control).setToolTip(control.toolTip())
        layout.addWidget(range_box)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    def _range_distance_combo(self, default, maximum, grouping=False):
        combo = QComboBox()
        combo.setEditable(True)
        values = [500, 1000, 2000, 5000, 10000, 20000]
        if grouping:
            values.extend([25000, 50000, 75000, 100000, 150000, 200000])
        else:
            values.extend([30000, 50000, 100000])
        combo.addItems([str(value) for value in values])
        combo.setCurrentText(str(default))
        combo.setValidator(QIntValidator(1, maximum, combo))
        return combo

    def _range_distance_value(self, combo):
        if not combo.lineEdit().hasAcceptableInput():
            raise ValueError("Enter a valid positive distance in metres / Introduce una distancia positiva valida en metros.")
        return combo.validator().locale().toInt(combo.currentText())[0]

    def reset_range_parameters(self):
        self.range_mode.setCurrentIndex(self.range_mode.findData("merge"))
        self.range_group_distance.setCurrentText("25000")
        self.range_concavity.setValue(0.80)
        self.range_smoothing.setValue(1)
        self.range_round_tips.setChecked(False)
        self.range_tip_radius.setCurrentText("2000")
        self.range_buffer.setCurrentText("2000")

    def remove_generated_aoo_eoo(self):
        project = QgsProject.instance()
        legacy_fields = {
            "AOO occupied cells": {"cell_id", "area_km2", "generalisd"},
            "EOO convex hull": {"method", "eoo_km2", "generalisd"},
            "AOO_EOO report summary": {name for name, _ in REPORT_FIELD_SPECS},
            "AOO_EOO unused records": {name for name, _ in EXCLUDED_FIELD_SPECS},
            "AOO_EOO points used": {name for name, _ in USED_POINT_FIELD_SPECS},
        }
        layer_ids = []
        for layer in project.mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            expected = legacy_fields.get(layer.name())
            if (layer.customProperty("iucn_generated_metric") in ("aoo", "eoo", "report")
                    or layer.customProperty("aoo_eoo_gbif_pro_layer_type") == "calculation_output"
                    or (layer.providerType() == "memory" and expected and expected <= set(layer.fields().names()))):
                layer_ids.append(layer.id())
        if layer_ids:
            project.removeMapLayers(layer_ids)
            self.refresh_calc_layers()
        self._log(f"AOO/EOO layers and report tables removed: {len(layer_ids)}.")

    def _make_report_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            'This tab prepares Point Distribution from the points used in the last calculation in tab 3. If you selected several layers in tab 3, the selected records from all of them will be included here.'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        csv_box = QGroupBox("Point Distribution")
        csv_layout = QVBoxLayout(csv_box)
        csv_hint = QLabel(
            'The Point Distribution table and CSV will have exactly 21 fields, in this order: sci_name, presence, origin, seasonal, compiler, yrcompiled, citation, dec_lat, dec_long, spatialref, subspecies, subpop, data_sens, sens_comm, event_year, source, basisofrec, catalog_no, dist_comm, island, tax_comm. The table and CSV use WGS84 longitude and latitude. The CRS selector controls the geometry of the QGIS layer and shapefile. Use WGS84 for SRedList.'
        )
        csv_hint.setWordWrap(True)
        csv_layout.addWidget(csv_hint)
        self.point_output_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.point_output_crs_button = QPushButton("Change layer CRS (EPSG:4326)")
        self.point_output_crs_button.setToolTip(
            "EN: Choose the CRS for the exported layer geometry. The decimal longitude and latitude fields stay in WGS84.\n"
            "ES: Elige el sistema de coordenadas para la geometría de la capa. Las columnas de longitud y latitud siguen en WGS84."
        )
        self.point_output_crs_button.clicked.connect(self._choose_point_output_crs)
        csv_layout.addWidget(self.point_output_crs_button)
        buttons = QGridLayout()
        self.create_point_distribution_button = QPushButton("Create Point Distribution table in QGIS")
        self.create_point_distribution_button.setToolTip("Create a Point Distribution attribute table in QGIS from the last calculation.\nES: Crea una tabla Point Distribution en QGIS a partir del último cálculo.")
        self.create_point_distribution_button.clicked.connect(self.create_point_distribution_table)
        self.create_point_distribution_shp_layer_button = QPushButton("Create Point Distribution layer in QGIS")
        self.create_point_distribution_shp_layer_button.setToolTip("Create a Point Distribution point layer compatible with the SRedList platform.\nES: Crea una capa de puntos Point Distribution compatible con la plataforma SRedList.")
        self.create_point_distribution_shp_layer_button.setToolTip("Create in QGIS a Point Distribution point layer compatible with the SRedList platform, using the points selected in the last calculation. Use EPSG:4326 for SRedList.\nES: Crea en QGIS una capa de puntos Point Distribution compatible con la plataforma SRedList, usando los puntos seleccionados del último cálculo.\nEN: SRedList accepts a binomial scientific name only (Genus species).\nES: SRedList solo admite un nombre científico binomial (Género especie).")
        self.create_point_distribution_shp_layer_button.clicked.connect(self.create_point_distribution_shapefile_layer)
        self.save_point_distribution_button = QPushButton("Save Point Distribution CSV (SRedList compatible)...")
        self.save_point_distribution_button.setToolTip("EN: Save the SRedList-compatible CSV in WGS84. Use a binomial scientific name (Genus species).\nES: Guarda el CSV compatible con SRedList en WGS84. Usa un nombre científico binomial (Género especie).")
        self.save_point_distribution_button.clicked.connect(self.save_point_distribution_csv)
        self.save_point_distribution_shp_button = QPushButton("Save Point Distribution shapefile...")
        self.save_point_distribution_shp_button.setToolTip("EN: Save the Point Distribution shapefile. SRedList accepts a binomial name only (Genus species).\nES: Guarda el shapefile Point Distribution. SRedList solo admite un nombre binomial (G\u00e9nero especie).")
        self.save_point_distribution_shp_button.clicked.connect(self.save_point_distribution_shapefile)
        self.point_distribution_help_button = QPushButton("Point Distribution field guide")
        self.point_distribution_help_button.setToolTip("Open a guide to the fields used in the Point Distribution output.\nES: Abre una guía de los campos utilizados en la salida Point Distribution.")
        self.point_distribution_help_button.clicked.connect(self.show_point_distribution_help)
        buttons.addWidget(self.create_point_distribution_button, 0, 0)
        buttons.addWidget(self.create_point_distribution_shp_layer_button, 0, 1)
        buttons.addWidget(self.save_point_distribution_button, 1, 0)
        buttons.addWidget(self.save_point_distribution_shp_button, 1, 1)
        buttons.addWidget(self.point_distribution_help_button, 2, 0, 1, 2)
        csv_layout.addLayout(buttons)
        layout.addWidget(csv_box)
        layout.addStretch(1)
        return tab


    def _make_gbif_citation_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        except AttributeError:
            pass
        content = QWidget()
        layout = QVBoxLayout(content)

        info = QLabel(
            'This tab creates the correct GBIF citation for the GBIF records that actually entered the calculation. The workflow uses only the official GBIF occurrence download route: used gbifIDs → official GBIF download → DOI → citation. It does not use Derived Dataset, datasetKey/count or an external public URL.'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        step1 = QGroupBox("Step 1. Prepare the used gbifIDs")
        step1_layout = QVBoxLayout(step1)
        step1_text = QLabel(
            'After calculating AOO/EOO, press the button to extract the gbifIDs from the points used. This is step 1 because GBIF needs the exact list of records used in the calculation. The list includes only GBIF records; user-added points do not have a GBIF DOI and must be cited separately.'
        )
        step1_text.setWordWrap(True)
        step1_layout.addWidget(step1_text)
        row1 = QHBoxLayout()
        self.prepare_gbif_ids_button = QPushButton("1. Prepare list of used gbifIDs")
        self.prepare_gbif_ids_button.setToolTip("Extract the gbifIDs actually used in the last calculation.\nES: Extrae los gbifID realmente usados en el último cálculo.")
        self.prepare_gbif_ids_button.clicked.connect(self.prepare_gbif_download_ids)
        self.copy_gbif_ids_button = QPushButton("Copy gbifID")
        self.copy_gbif_ids_button.setToolTip("Copy the used gbifIDs to the clipboard for review.\nES: Copia los gbifID usados al portapapeles para revisión.")
        self.copy_gbif_ids_button.clicked.connect(self.copy_gbif_ids)
        row1.addWidget(self.prepare_gbif_ids_button)
        row1.addWidget(self.copy_gbif_ids_button)
        row1.addStretch(1)
        step1_layout.addLayout(row1)
        layout.addWidget(step1)

        step2 = QGroupBox("Step 2. Request an official GBIF download")
        step2_layout = QVBoxLayout(step2)
        step2_text = QLabel(
            'With this option you do not need to paste the list into any website: the plugin sends it directly to the official GBIF download API. GBIF first returns a download key. The DOI appears when the download is finished. You need your GBIF.org username and password; the password is not stored.'
        )
        step2_text.setWordWrap(True)
        step2_layout.addWidget(step2_text)
        form_box = QWidget()
        form = QFormLayout(form_box)
        _set_form_expanding_fields(form)
        self.gbif_download_user = QLineEdit()
        self.gbif_download_user.setPlaceholderText("GBIF username, not email")
        self.gbif_download_password = QLineEdit()
        self.gbif_download_password.setEchoMode(_line_edit_password())
        self.gbif_download_email = QLineEdit()
        self.gbif_download_email.setPlaceholderText("GBIF notification email")
        self.gbif_download_format = QComboBox()
        self.gbif_download_format.addItem("SIMPLE_CSV", "SIMPLE_CSV")
        self.gbif_download_format.addItem("DWCA", "DWCA")
        form.addRow("GBIF username* (not email)", self.gbif_download_user)
        form.addRow("GBIF password*", self.gbif_download_password)
        form.addRow("Notification email", self.gbif_download_email)
        form.addRow("Format", self.gbif_download_format)
        step2_layout.addWidget(form_box)
        row2 = QHBoxLayout()
        self.request_gbif_download_button = QPushButton("2. Request official download and DOI")
        self.request_gbif_download_button.setToolTip("Send the used gbifIDs to the official GBIF download API in order to obtain a DOI.\nES: Envía los gbifID usados a la API oficial de descargas de GBIF para obtener un DOI.")
        self.request_gbif_download_button.clicked.connect(self.request_gbif_occurrence_download)
        self.open_gbif_download_button = QPushButton("Open my GBIF downloads")
        self.open_gbif_download_button.setToolTip("Open the GBIF page with your downloads in the browser.\nES: Abre en el navegador la página de GBIF con tus descargas.")
        self.open_gbif_download_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.gbif.org/occurrence/download")))
        row2.addWidget(self.request_gbif_download_button)
        row2.addWidget(self.open_gbif_download_button)
        row2.addStretch(1)
        step2_layout.addLayout(row2)
        layout.addWidget(step2)

        step3 = QGroupBox("Step 3. Check whether the DOI is ready")
        step3_layout = QVBoxLayout(step3)
        step3_text = QLabel(
            'The GBIF download is asynchronous. It may take from a few seconds to several minutes. When the status is SUCCEEDED, GBIF will return a citable DOI.'
        )
        step3_text.setWordWrap(True)
        step3_layout.addWidget(step3_text)
        key_row = QHBoxLayout()
        self.gbif_download_key_edit = QLineEdit()
        self.gbif_download_key_edit.setPlaceholderText("GBIF download key")
        self.check_gbif_download_button = QPushButton("3. Check status / DOI")
        self.check_gbif_download_button.setToolTip("Check the status of the GBIF download and retrieve the DOI when ready.\nES: Comprueba el estado de la descarga de GBIF y recupera el DOI cuando esté listo.")
        self.check_gbif_download_button.clicked.connect(self.check_gbif_occurrence_download)
        key_row.addWidget(QLabel("Key:"))
        key_row.addWidget(self.gbif_download_key_edit, 1)
        key_row.addWidget(self.check_gbif_download_button)
        step3_layout.addLayout(key_row)
        layout.addWidget(step3)

        step4 = QGroupBox("Step 4. Result and citation")
        step4_layout = QVBoxLayout(step4)
        self.gbif_download_result = QTextEdit()
        self.gbif_download_result.setReadOnly(True)
        self.gbif_download_result.setMinimumHeight(220)
        self.gbif_download_result.setPlainText(
            "EN:\n"
            "1) Calculate AOO/EOO in tab 3.\n"
            "2) Press ‘Prepare list of used gbifIDs’.\n"
            "3) Enter your GBIF username/password and request the official download.\n"
            "4) Copy the download key or press ‘Check status / DOI’ until GBIF returns SUCCEEDED.\n"
            "5) Cite the GBIF DOI that will appear here.\n\n"
            "Note: the GBIF DOI covers only records coming from GBIF. User-added points must be cited with their own independent source.\n\n"
            "ES:\n"
            "1) Calcula AOO/EOO en la pestaña 3.\n"
            "2) Pulsa ‘Prepare list of used gbifIDs’.\n"
            "3) Introduce tu usuario/contraseña de GBIF y solicita la descarga oficial.\n"
            "4) Copia la clave de descarga o pulsa ‘Check status / DOI’ hasta que GBIF devuelva SUCCEEDED.\n"
            "5) Cita el DOI de GBIF que aparecerá aquí.\n\n"
            "Nota: el DOI GBIF cubre únicamente los registros procedentes de GBIF. Los puntos propios deben citarse con su fuente independiente."
        )
        step4_layout.addWidget(self.gbif_download_result)
        row4 = QHBoxLayout()
        self.copy_gbif_citation_button = QPushButton("Copy citation")
        self.copy_gbif_citation_button.setToolTip("Copy the recommended GBIF citation to the clipboard.\nES: Copia la cita recomendada de GBIF al portapapeles.")
        self.copy_gbif_citation_button.clicked.connect(self.copy_gbif_citation)
        self.open_gbif_citation_button = QPushButton("Open GBIF citation guide")
        self.open_gbif_citation_button.setToolTip("Open the official GBIF guidance on citing downloads.\nES: Abre la guía oficial de GBIF sobre cómo citar descargas.")
        self.open_gbif_citation_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.gbif.org/citation-guidelines")))
        row4.addWidget(self.copy_gbif_citation_button)
        row4.addWidget(self.open_gbif_citation_button)
        row4.addStretch(1)
        step4_layout.addLayout(row4)
        layout.addWidget(step4)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return tab

    def _make_check_list(self, options) -> QListWidget:
        widget = QListWidget()
        for value, checked, tooltip in options:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | _qt_item_user_checkable())
            item.setCheckState(_qt_checked() if checked else _qt_unchecked())
            item.setToolTip(tooltip)
            widget.addItem(item)
        return widget

    def show_point_distribution_help(self):
        dialog = PointDistributionHelpDialog(self)
        _dialog_exec(dialog)


    def reset_gbif_filters(self):
        """Restore filter defaults for the current search."""
        self.gbif_require_year.setChecked(False)
        self.gbif_excluded_publishers.clear()
        self.gbif_excluded_collections.clear()
        self.gbif_collections_button.setText("Exclude collections (0)")
        self.gbif_publishers_button.setText("Exclude data publishers (0)")
        self.gbif_require_uncertainty.setChecked(False)
        self._remove_gbif_preview()
        self.country_code.clear()
        self.year_min.setValue(0)
        self.year_max.setValue(0)
        self.occurrence_status.setCurrentIndex(0)
        self.exclude_geospatial_issues.setChecked(True)
        self.coordinatecleaner_filter.setChecked(True)
        if hasattr(self, "gbif_uncertainty_filter"):
            self.gbif_uncertainty_filter.setChecked(False)
        if hasattr(self, "gbif_uncertainty_combo"):
            self.gbif_uncertainty_combo.setCurrentText("1 km")
        for list_widget, options in [(self.basis_list, BASIS_OPTIONS), (self.establishment_list, ESTABLISHMENT_OPTIONS)]:
            for i, (_value, checked, _tooltip) in enumerate(options):
                item = list_widget.item(i)
                if item is not None:
                    item.setCheckState(_qt_checked() if checked else _qt_unchecked())
        self.filter_establishment.setChecked(False)
        self._log("GBIF filters restored to defaults.")


    def reset_gbif_tab(self):
        """Clear the search form and visible output."""
        self.reset_gbif_filters()
        self.scientific_name.clear()
        self.taxon_key.clear()
        self.assess_infraspecific.setChecked(False)
        self.infraspecific_epithet.clear()
        for widget in (self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4):
            widget.clear()
        self.last_filter_removed = []
        self.log.clear()


    # ------------------------------------------------------------- utilities
    def _log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{stamp}] {text}")

    def _checked_values(self, widget: QListWidget) -> list[str]:
        values = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == _qt_checked():
                values.append(item.text())
        return values

    def _synonym_names(self) -> list[str]:
        names = []
        for widget in [self.synonym_1, self.synonym_2, self.synonym_3, self.synonym_4]:
            value = widget.text().strip()
            if value and value not in names:
                names.append(value)
        return names

    def _gbif_uncertainty_threshold_m(self):
        text = self.gbif_uncertainty_combo.currentText().strip().lower()
        if text == "no limit":
            return None
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(m|km)?", text)
        if not match:
            raise ValueError("Enter a non-negative uncertainty threshold in metres or kilometres (e.g. 500 m).")
        value = float(match.group(1).replace(",", "."))
        return value * 1000 if match.group(2) == "km" else value

    def _gbif_year_bounds(self):
        ymin = self.year_min.value() if hasattr(self, "year_min") and self.year_min.value() else None
        ymax = self.year_max.value() if hasattr(self, "year_max") and self.year_max.value() else None
        return ymin, ymax

    def _apply_local_year_filter(self, records):
        ymin, ymax = self._gbif_year_bounds()
        require_year = self.gbif_require_year.isChecked()
        if ymin is None and ymax is None and not require_year:
            return records, []
        kept = []
        removed = []
        for rec in records:
            raw_year = rec.get("year")
            try:
                year_value = int(raw_year) if raw_year not in (None, "") else None
            except (TypeError, ValueError):
                year_value = None
            if year_value is None or year_value <= 0:
                if require_year:
                    removed.append((rec, "Year filter: missing or invalid occurrence year"))
                else:
                    kept.append(rec)
                continue
            if ymin is not None and year_value < ymin:
                removed.append((rec, f"Year filter: {year_value} < minimum year {ymin}"))
            elif ymax is not None and year_value > ymax:
                removed.append((rec, f"Year filter: {year_value} > maximum year {ymax}"))
            else:
                kept.append(rec)
        return kept, removed

    def _build_gbif_params(self) -> dict:
        params = {"hasCoordinate": "true"}
        taxon_key = self.taxon_key.text().strip()
        if taxon_key:
            params["taxonKey"] = taxon_key
        else:
            name = self.scientific_name.text().strip()
            if not name:
                raise ValueError("Enter a scientific name or a taxonKey.")
            # GBIF can search by scientificName, but taxonKey is more reproducible.
            params["scientificName"] = name

        if self.country_code.text().strip():
            params["country"] = self.country_code.text().strip().upper()

        # El filtro de año se aplica localmente después de descargar los registros,
        # para que los registros descartados puedan auditarse en la tabla
        # “GBIF registros eliminados por filtros”.
        # Use the canonical query value rather than the displayed bilingual label.
        selected_status = self.occurrence_status.currentData()
        if selected_status:
            params["occurrenceStatus"] = selected_status

        basis = self._checked_values(self.basis_list)
        if basis:
            params["basisOfRecord"] = basis

        if self.filter_establishment.isChecked():
            est = self._checked_values(self.establishment_list)
            if est:
                params["establishmentMeans"] = est

        if self.exclude_geospatial_issues.isChecked():
            params["hasGeospatialIssue"] = "false"
        return params


    def _motivo_coordinatecleaner_es(self, reason: str) -> str:
        return COORDINATECLEANER_REASON_TRANSLATION.get(str(reason or ""), str(reason or ""))

    def create_coordinatecleaner_criteria_table(self):
        """Crea una tabla en QGIS con los criterios del filtro CoordinateCleaner aplicado."""
        layer = QgsVectorLayer("None", "Criterios del filtro CoordinateCleaner", "memory")
        provider = layer.dataProvider()
        provider.addAttributes([
            QgsField("motivo", QVariant.String),
            QgsField("que_elimina", QVariant.String),
        ])
        layer.updateFields()
        features = []
        for motivo, descripcion in COORDINATECLEANER_CRITERIOS_ES:
            feat = QgsFeature(layer.fields())
            feat.setAttributes([motivo, descripcion])
            features.append(feat)
        provider.addFeatures(features)
        layer.updateFields()
        layer.updateExtents()
        layer.setCustomProperty("iucn_geojson_output", True)
        QgsProject.instance().addMapLayer(layer)
        self._log("CoordinateCleaner-like criteria table created.")
        self.iface.messageBar().pushSuccess("IUCN Red List calculator", "Filter criteria table added to the project.")

    def create_filtered_records_table(self):
        """Crea una tabla en QGIS con los registros retirados por filtros automáticos."""
        removed = getattr(self, "last_filter_removed", []) or []
        if not removed:
            QMessageBox.information(
                self,
                "Removed records",
                "There are no records removed by the year, CoordinateCleaner or uncertainty filters in the last GBIF download."
            )
            return

        layer = QgsVectorLayer("None", "GBIF registros eliminados por filtros", "memory")
        provider = layer.dataProvider()
        fields = [
            ("motivo", QVariant.String),
            ("gbifID", QVariant.String),
            ("nombre_cientifico", QVariant.String),
            ("latitud", QVariant.Double),
            ("longitud", QVariant.Double),
            ("incertidumbre_m", QVariant.Double),
            ("base_registro", QVariant.String),
            ("estado_ocurrencia", QVariant.String),
            ("origen_establecimiento", QVariant.String),
            ("fecha_evento", QVariant.String),
            ("anio", QVariant.Int),
            ("pais", QVariant.String),
            ("datasetKey", QVariant.String),
            ("institucion", QVariant.String),
            ("coleccion", QVariant.String),
            ("incidencias_gbif", QVariant.String),
        ]
        provider.addAttributes([QgsField(name, typ) for name, typ in fields])
        layer.updateFields()

        def safe_float(value):
            try:
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def safe_int(value):
            try:
                if value in (None, ""):
                    return None
                return int(value)
            except (TypeError, ValueError):
                return None

        features = []
        for rec, reason in removed:
            reason_text = str(reason or "")
            if reason_text.startswith("CoordinateCleaner: "):
                raw_reason = reason_text.split(": ", 1)[1]
                reason_text = "CoordinateCleaner: " + self._motivo_coordinatecleaner_es(raw_reason)
            feat = QgsFeature(layer.fields())
            feat.setAttributes([
                reason_text,
                str(rec.get("gbifID", "") or ""),
                str(rec.get("scientificName", "") or ""),
                safe_float(rec.get("decimalLatitude")),
                safe_float(rec.get("decimalLongitude")),
                safe_float(rec.get("coordinateUncertaintyInMeters")),
                str(rec.get("basisOfRecord", "") or ""),
                str(rec.get("occurrenceStatus", "") or ""),
                str(rec.get("establishmentMeans", "") or ""),
                str(rec.get("eventDate", "") or ""),
                safe_int(rec.get("year")),
                str(rec.get("countryCode", "") or ""),
                str(rec.get("datasetKey", "") or ""),
                str(rec.get("institutionCode", "") or ""),
                str(rec.get("collectionCode", "") or ""),
                str(rec.get("issues", "") or ""),
            ])
            features.append(feat)
        provider.addFeatures(features)
        layer.updateFields()
        layer.updateExtents()
        layer.setCustomProperty("iucn_geojson_output", True)
        QgsProject.instance().addMapLayer(layer)
        self._log(f"Table created with {len(features)} records removed by automatic filters.")
        self.iface.messageBar().pushSuccess("IUCN Red List calculator", "Removed-records table added to the project.")

    # -------------------------------------------------------------- GBIF ops
    def resolve_taxon(self):
        try:
            result = match_species(self.scientific_name.text().strip())
        except GbifError as exc:
            QMessageBox.warning(self, "GBIF", str(exc))
            return

        usage_key = result.get("usageKey") or result.get("acceptedUsageKey")
        if usage_key:
            self.taxon_key.setText(str(usage_key))
        msg = (
            f"Match GBIF: {result.get('scientificName', '')} | "
            f"rank={result.get('rank', '')} | confidence={result.get('confidence', '')} | "
            f"status={result.get('status', '')} | usageKey={usage_key}"
        )
        self._log(msg)

    def _read_filtered_gbif(self, apply_publisher_filter=True, cancellable=False, apply_collection_filter=True):
        from qgis.PyQt.QtCore import QEventLoop
        _exclude_user_input = getattr(QEventLoop, "ProcessEventsFlag", QEventLoop).ExcludeUserInputEvents
        params = self._build_gbif_params()
        threshold = self._gbif_uncertainty_threshold_m() if self.gbif_uncertainty_filter.isChecked() else None
        self._log(f"Querying GBIF with main parameters: {params}")

        def progress(done, total):
            total_txt = total if total is not None else "?"
            self._log(f"  downloaded {done} of {total_txt}")
            if cancellable:
                QApplication.processEvents()
                if self.gbif_query_cancelled:
                    raise InterruptedError()
            else:
                QApplication.processEvents(_exclude_user_input)

        raw_records = search_occurrences(params, progress_callback=progress)

        # Optional synonyms: GBIF occurrence/search has no single OR widget here,
        # so we query each synonym separately and deduplicate by gbifID.
        synonyms = self._synonym_names()
        if synonyms:
            self._log(f"Also searching synonyms: {', '.join(synonyms)}")
            for syn in synonyms:
                syn_params = dict(params)
                syn_params.pop("taxonKey", None)
                syn_params["scientificName"] = syn
                self._log(f"  Downloading synonym: {syn}")
                raw_records.extend(search_occurrences(syn_params, progress_callback=progress))

        # Deduplicate GBIF records before creating the QGIS layer.
        seen_gbif_ids = set()
        slim_records = []
        for record in raw_records:
            rec = slim_record(record)
            gbif_id = rec.get("gbifID", "")
            if gbif_id and gbif_id in seen_gbif_ids:
                continue
            if gbif_id:
                seen_gbif_ids.add(gbif_id)
            slim_records.append(rec)

        removed = []
        records = slim_records

        records, removed_year = self._apply_local_year_filter(records)
        if removed_year:
            removed.extend(removed_year)
            self._log(f"Year filter applied: {len(removed_year)} records removed by local filters.")
        elif self.year_min.value() or self.year_max.value():
            self._log("Year filter applied: no records removed.")

        if self.coordinatecleaner_filter.isChecked():
            records, flagged = coordinatecleaner_filter_records(records)
            for rec, reason in flagged:
                removed.append((rec, f"CoordinateCleaner: {self._motivo_coordinatecleaner_es(reason)}"))
            self._log(f"CoordinateCleaner-like filter applied: {len(flagged)} records excluded by local filters.")
            if flagged:
                reasons = {}
                for _rec, reason in flagged:
                    reason_es = self._motivo_coordinatecleaner_es(reason)
                    reasons[reason_es] = reasons.get(reason_es, 0) + 1
                self._log("  Reasons: " + "; ".join(f"{k}={v}" for k, v in sorted(reasons.items())))

        require_uncertainty = self.gbif_require_uncertainty.isChecked()
        if threshold is not None or require_uncertainty:
            kept = []
            for rec in records:
                try:
                    value = float(rec.get("coordinateUncertaintyInMeters"))
                    if not math.isfinite(value) or value < 0:
                        value = None
                except (TypeError, ValueError):
                    value = None
                if value is None and require_uncertainty:
                    removed.append((rec, "Coordinate uncertainty: missing or invalid value"))
                elif value is not None and threshold is not None and value > threshold:
                    removed.append((rec, f"Coordinate uncertainty: {value:g} m > {threshold:g} m"))
                else:
                    kept.append(rec)
            self._log(f"Coordinate uncertainty filter: {len(records) - len(kept)} records excluded.")
            records = kept

        kept = []
        for rec in records:
            key = rec["publishingOrgKey"]
            name = self.gbif_publisher_names.get(key, "")
            rec["publisher"] = name
            if apply_publisher_filter and key in self.gbif_excluded_publishers:
                removed.append((rec, f"Excluded GBIF data publisher: {name or key}"))
            elif apply_collection_filter and self._gbif_collection_key(rec) in self.gbif_excluded_collections:
                label = self.gbif_excluded_collections[self._gbif_collection_key(rec)]
                removed.append((rec, f"Excluded GBIF collection: {label}"))
            else:
                kept.append(rec)
        records = kept

        self._log(f"GBIF records after filters: {len(records)} / {len(slim_records)} unique records returned "
                  f"by the GBIF query ({len(removed)} excluded locally).")
        return records, removed

    def _choose_excluded_publishers(self):
        try:
            records, _ = self._read_filtered_gbif(apply_publisher_filter=False, apply_collection_filter=False)
        except (GbifError, ValueError) as exc:
            QMessageBox.warning(self, "GBIF data publishers", str(exc))
            return
        counts = {}
        for rec in records:
            key = rec["publishingOrgKey"]
            if key:
                counts[key] = counts.get(key, 0) + 1
        keys = counts.keys() | self.gbif_excluded_publishers
        if not keys:
            QMessageBox.information(self, "GBIF data publishers", "No identifiable publishers for this search.")
            return
        for key in sorted(keys):
            if key not in self.gbif_publisher_names:
                try:
                    self.gbif_publisher_names[key] = publishing_organization_name(key)
                except GbifError:
                    self._log(f"GBIF publisher name unavailable: {key}")
        labels = {key: self.gbif_publisher_names.get(key, key) for key in keys}
        selected = self._choose_gbif_exclusions("data publishers", labels, counts, self.gbif_excluded_publishers)
        if selected is not None:
            self.gbif_excluded_publishers = selected
            self._remove_gbif_preview()
            self.gbif_publishers_button.setText(f"Exclude data publishers ({len(selected)})")

    def _gbif_collection_key(self, record):
        if record["collectionKey"]:
            return ("key", record["collectionKey"])
        code = record["collectionCode"].strip().casefold()
        if code:
            return ("code", record["publishingOrgKey"], record["datasetKey"],
                    record["institutionCode"].strip().casefold(), code)
        return None

    def _choose_excluded_collections(self):
        try:
            records, _ = self._read_filtered_gbif(apply_collection_filter=False)
        except (GbifError, ValueError) as exc:
            QMessageBox.warning(self, "GBIF collections", str(exc))
            return
        labels = dict(self.gbif_excluded_collections)
        counts = {}
        for rec in records:
            key = self._gbif_collection_key(rec)
            if key is None:
                continue
            code = rec["collectionCode"].strip() or rec["collectionKey"]
            institution = rec["institutionCode"].strip()
            source = rec.get("publisher") or rec["datasetKey"] or rec["publishingOrgKey"]
            labels.setdefault(key, " | ".join(value for value in (code, institution, source) if value))
            counts[key] = counts.get(key, 0) + 1
        if not labels:
            QMessageBox.information(self, "GBIF collections", "No identifiable collections for this search.")
            return
        selected = self._choose_gbif_exclusions("collections", labels, counts, self.gbif_excluded_collections)
        if selected is not None:
            self.gbif_excluded_collections = {key: labels[key] for key in selected}
            self._remove_gbif_preview()
            self.gbif_collections_button.setText(f"Exclude collections ({len(selected)})")

    def _choose_gbif_exclusions(self, title, labels, counts, excluded):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Exclude GBIF {title}")
        dialog.resize(680, 400)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Tick the entries to exclude / Marca las opciones que quieres excluir"))
        items = QListWidget()
        keys = sorted(labels, key=lambda key: (labels[key].casefold(), str(key)))
        for key in keys:
            item = QListWidgetItem(f"{labels[key]} ({counts.get(key, 0):,})")
            item.setToolTip(str(key))
            item.setFlags(item.flags() | _qt_item_user_checkable())
            item.setCheckState(_qt_checked() if key in excluded else _qt_unchecked())
            items.addItem(item)
        layout.addWidget(items)
        buttons = QDialogButtonBox(_button_box_ok() | _button_box_cancel())
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if _dialog_exec(dialog) != _dialog_accepted():
            return None
        return {key for index, key in enumerate(keys) if items.item(index).checkState() == _qt_checked()}

    def preview_facets(self):
        try:
            records, removed = self._read_cancellable_gbif()
            mapped = create_occurrence_layer(records).featureCount()
            QMessageBox.information(
                self, "GBIF counts with filters",
                f"Points ready to import: {mapped:,}\n"
                f"After all filters: {len(records):,}\n"
                f"After GBIF server filters, before local filters: {len(records) + len(removed):,}\n"
                f"Excluded by local filters: {len(removed):,}",
            )
        except InterruptedError:
            self._log("GBIF count preview cancelled. Partial records were discarded.")
        except (GbifError, ValueError) as exc:
            QMessageBox.warning(self, "GBIF", str(exc))

    def _remove_gbif_preview(self):
        project = QgsProject.instance()
        if self.gbif_preview_id and project.mapLayer(self.gbif_preview_id):
            project.removeMapLayer(self.gbif_preview_id)
        self.gbif_preview_id = None

    def preview_gbif_records(self):
        try:
            records, _ = self._read_cancellable_gbif()
            layer = create_occurrence_layer(records, "PREVIEW - filtered GBIF occurrences")
            layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "gbif_preview")
            self._remove_gbif_preview()
            QgsProject.instance().addMapLayer(layer)
            self.gbif_preview_id = layer.id()
            self.iface.showAttributeTable(layer)
        except InterruptedError:
            self._log("GBIF record preview cancelled. Partial records were discarded.")
        except (GbifError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "GBIF preview", str(exc))

    def _stop_gbif_query(self):
        self.gbif_query_cancelled = True
        self.stop_gbif_button.setEnabled(False)

    def _read_cancellable_gbif(self):
        self.gbif_query_cancelled = False
        tab = self.tabs.widget(0)
        controls = [
            widget for widget in tab.findChildren(QWidget)
            if widget.parentWidget() is tab and widget is not self.stop_gbif_button and widget.isEnabled()
        ]
        for widget in controls:
            widget.setEnabled(False)
        self.stop_gbif_button.setEnabled(True)
        try:
            result = self._read_filtered_gbif(cancellable=True)
            QApplication.processEvents()
            if self.gbif_query_cancelled:
                raise InterruptedError()
            return result
        finally:
            self.stop_gbif_button.setEnabled(False)
            for widget in controls:
                widget.setEnabled(True)

    def download_gbif(self):
        try:
            records, removed = self._read_cancellable_gbif()
            layer_name = "GBIF occurrences AOO_EOO"
            if self.scientific_name.text().strip():
                layer_name = f"GBIF {self.scientific_name.text().strip()}"
            self.gbif_layer = create_occurrence_layer(records, layer_name)
            self.last_filter_removed = removed
            self._remove_gbif_preview()
            self.gbif_layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "gbif_points")
            QgsProject.instance().addMapLayer(self.gbif_layer)
            self.gbif_layer_id = self.gbif_layer.id()
            if self.layer_combo is not None:
                self.layer_combo.setLayer(self.gbif_layer)
            self.refresh_calc_layers(apply_defaults=False)
            self._log(f"GBIF layer created: {self.gbif_layer.featureCount()} valid points with coordinates.")
            self.iface.messageBar().pushSuccess("IUCN Red List calculator", "GBIF download finished and added to the project.")
        except InterruptedError:
            self._log("GBIF download cancelled. Partial records were discarded.")
        except (GbifError, ValueError, Exception) as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "GBIF download error", str(exc))
            self._log(f"ERROR GBIF: {exc}")

    # -------------------------------------------------------------- GBIF layer
    def _get_existing_gbif_layer(self):
        """Return the current GBIF occurrence layer, or None if it was removed."""
        if _layer_is_usable(self.gbif_layer):
            return self.gbif_layer

        self.gbif_layer = None
        project = QgsProject.instance()

        if self.gbif_layer_id:
            layer = project.mapLayer(self.gbif_layer_id)
            if _layer_is_usable(layer):
                self.gbif_layer = layer
                return layer
            self.gbif_layer_id = None

        for layer in project.mapLayers().values():
            try:
                if layer.customProperty("aoo_eoo_gbif_pro_layer_type") == "gbif_points" and _layer_is_usable(layer):
                    self.gbif_layer = layer
                    self.gbif_layer_id = layer.id()
                    return layer
            except RuntimeError:
                continue
        return None


    # ------------------------------------------------------------- layer selection
    def _is_probably_point_layer(self, layer) -> bool:
        if not isinstance(layer, QgsVectorLayer) or not _layer_is_usable(layer):
            return False
        if layer.customProperty("aoo_eoo_gbif_pro_layer_type") in ("gbif_preview", "calculation_output", "point_distribution_output"):
            return False
        geometry_types = getattr(Qgis, "GeometryType", None)
        point_type = geometry_types.Point if geometry_types is not None else QgsWkbTypes.PointGeometry
        return layer.geometryType() == point_type

    def _update_calc_selection_summary(self, _changed_item=None):
        """Display the exact input selection, independently of QGIS layer visibility."""
        if self.calc_layers_list is None:
            return
        selected = [self.calc_layers_list.item(i).text()
                    for i in range(self.calc_layers_list.count())
                    if self.calc_layers_list.item(i).checkState() == _qt_checked()]
        label = "; ".join(selected) if selected else "none / ninguna"
        self.calc_selection_summary.setText(
            f"Selected for calculation / Capas seleccionadas ({len(selected)}): {label}"
        )

    def refresh_calc_layers(self, apply_defaults=None):
        """Select new point layers by default and preserve existing choices."""
        if self.calc_layers_list is None:
            return
        previous = {
            self.calc_layers_list.item(i).data(_qt_user_role()): self.calc_layers_list.item(i).checkState()
            for i in range(self.calc_layers_list.count())
        }
        self.calc_layers_list.blockSignals(True)
        try:
            self.calc_layers_list.clear()
            for layer in QgsProject.instance().mapLayers().values():
                if not self._is_probably_point_layer(layer):
                    continue
                try:
                    item = QListWidgetItem(f"{layer.name()} ({layer.featureCount()} records)")
                    item.setFlags(_qt_item_is_enabled() | _qt_item_is_selectable() | _qt_item_user_checkable())
                    item.setData(_qt_user_role(), layer.id())
                    item.setToolTip(f"{layer.name()} | {layer.source() if hasattr(layer, 'source') else ''}")
                    item.setCheckState(previous.get(layer.id(), _qt_checked()))
                    self.calc_layers_list.addItem(item)
                except RuntimeError as exc:
                    self._log(f"A deleted or unavailable layer was skipped during refresh: {exc}")
        finally:
            self.calc_layers_list.blockSignals(False)
        self._update_calc_selection_summary()

    def check_current_calc_layer(self):
        if self.calc_layers_list is None:
            return
        self.refresh_calc_layers(apply_defaults=False)
        try:
            fallback = self.layer_combo.currentLayer() if self.layer_combo is not None else None
            current = self.iface.activeLayer() or fallback
            current_id = current.id() if _layer_is_usable(current) else ""
        except Exception:
            current_id = ""
        if not current_id:
            return
        for i in range(self.calc_layers_list.count()):
            item = self.calc_layers_list.item(i)
            if item.data(_qt_user_role()) == current_id:
                item.setCheckState(_qt_checked())

    def check_all_calc_layers(self):
        if self.calc_layers_list is None:
            return
        self.refresh_calc_layers(apply_defaults=False)
        for i in range(self.calc_layers_list.count()):
            self.calc_layers_list.item(i).setCheckState(_qt_checked())

    def uncheck_all_calc_layers(self):
        if self.calc_layers_list is None:
            return
        for i in range(self.calc_layers_list.count()):
            self.calc_layers_list.item(i).setCheckState(_qt_unchecked())

    def _on_tab_changed(self, index):
        # Do not auto-refresh tab 3 when it is opened. The layer list should not
        # show old project/test layers by default; it is refreshed explicitly with
        # the button or automatically only after this plugin creates/imports data.
        return

    def _selected_calc_layers(self):
        layers = []
        project = QgsProject.instance()
        if self.calc_layers_list is not None:
            for i in range(self.calc_layers_list.count()):
                item = self.calc_layers_list.item(i)
                if item.checkState() != _qt_checked():
                    continue
                layer = project.mapLayer(item.data(_qt_user_role()))
                if _layer_is_usable(layer) and layer not in layers:
                    layers.append(layer)
        return layers

    def _iucn_criterion_b_inputs(self):
        # Se conserva por compatibilidad interna, pero la versión actual solo
        # informa la categoría orientativa según umbrales de AOO y EOO.
        return {}

    # ------------------------------------------------------------- manual ops
    def _get_existing_manual_layer(self):
        """Return the current layer for user-added points, or None if it was removed."""
        if _layer_is_usable(self.manual_layer):
            return self.manual_layer

        self.manual_layer = None
        project = QgsProject.instance()

        if self.manual_layer_id:
            layer = project.mapLayer(self.manual_layer_id)
            if _layer_is_usable(layer):
                self.manual_layer = layer
                return layer
            self.manual_layer_id = None

        for layer in project.mapLayers().values():
            try:
                if layer.customProperty("aoo_eoo_gbif_pro_layer_type") == "manual_points" and _layer_is_usable(layer):
                    self.manual_layer = layer
                    self.manual_layer_id = layer.id()
                    return layer
            except RuntimeError:
                continue
        return None

    def _ensure_manual_layer(self):
        layer = self._get_existing_manual_layer()
        if layer is None:
            layer = create_manual_layer()
            layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "manual_points")
            QgsProject.instance().addMapLayer(layer)
            self.manual_layer = layer
            self.manual_layer_id = layer.id()
        self.manual_status.setText(f"User points layer active: {_layer_name(layer)}")
        return layer

    def activate_manual_point_tool(self):
        # The temporary manual layer is only created after the first point is
        # confirmed, not merely when the map-click tool is activated.
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualPointTool(self.iface.mapCanvas(), self._manual_point_clicked)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Click on the map to add a point. A form will open before saving it.")

    def activate_manual_delete_tool(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Added points", "No valid user-points layer was found for deletion.")
            return
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualPointTool(self.iface.mapCanvas(), self._manual_delete_clicked)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Click near a manually added point to delete it from the layer.")

    def activate_manual_delete_area_tool(self):
        layer = self._ensure_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Added points", "No valid user-points layer was found for deletion.")
            return
        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.manual_tool = ManualRectangleTool(self.iface.mapCanvas(), self._manual_delete_area_selected)
        self.iface.mapCanvas().setMapTool(self.manual_tool)
        self._log("Drag a rectangle on the map to delete the user points contained in that area.")

    def _manual_delete_area_selected(self, rect):
        layer = self._get_existing_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Added points", "The user-points layer does not exist.")
            return
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = layer.crs()
        try:
            selection_geom = QgsGeometry.fromRect(rect)
            if canvas_crs != target_crs:
                selection_geom.transform(QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance()))
        except Exception as exc:
            QMessageBox.warning(self, "Delete points", f"The selection area could not be transformed: {exc}")
            return

        # If the user only clicks, the rectangle can be nearly empty. Expand it
        # slightly so it still behaves like an easier point-deletion tool.
        try:
            bbox = selection_geom.boundingBox()
            if bbox.width() == 0 and bbox.height() == 0:
                center = bbox.center()
                tol = 0.001 if target_crs.isGeographic() else max(20.0, self.iface.mapCanvas().mapUnitsPerPixel() * 20.0)
                selection_geom = QgsGeometry.fromRect(QgsRectangle(center.x() - tol, center.y() - tol, center.x() + tol, center.y() + tol))
        except (AttributeError, RuntimeError, ValueError) as exc:
            self._log(f"ERROR expanding point-deletion selection: {exc}")
            QMessageBox.warning(self, "Delete points", f"The selection area could not be prepared: {exc}")
            return

        fids = []
        skipped_geometries = 0
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                if selection_geom.intersects(geom):
                    fids.append(feat.id())
            except (RuntimeError, ValueError, TypeError) as exc:
                skipped_geometries += 1
                self._log(f"Skipping feature {feat.id()} during area selection: {exc}")

        if skipped_geometries:
            QMessageBox.warning(
                self, "Delete points",
                f"Could not check {skipped_geometries} feature(s) due to geometry errors. "
                "No points have been deleted. Repair the geometries and retry."
            )
            return
        if not fids:
            QMessageBox.information(self, "Added points", "There are no user points inside the selected area.")
            return

        reply = QMessageBox.question(
            self,
            "Delete points",
            f"Delete {len(fids)} user point(s) inside the selected area?",
            _messagebox_yes() | _messagebox_no(),
            _messagebox_no(),
        )
        if reply != _messagebox_yes():
            return

        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        ok = layer.deleteFeatures(fids)
        if not was_editing:
            layer.commitChanges()
        layer.updateExtents()
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()
        if ok:
            self.refresh_calc_layers(apply_defaults=False)
            self._log(f"User points deleted by area: {len(fids)}")
        else:
            QMessageBox.warning(self, "Added points", "QGIS could not delete the selected points.")

    def _manual_delete_clicked(self, point, button):
        layer = self._get_existing_manual_layer()
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Added points", "The user-points layer does not exist.")
            return
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = layer.crs()
        click_point = QgsPointXY(point)
        if canvas_crs != target_crs:
            click_point = QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance()).transform(click_point)
        click_geom = QgsGeometry.fromPointXY(click_point)
        best_fid = None
        best_dist = None
        skipped_geometries = 0
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                dist = geom.distance(click_geom)
            except (RuntimeError, ValueError, TypeError) as exc:
                skipped_geometries += 1
                self._log(f"Skipping feature {feat.id()} during nearest-point search: {exc}")
            else:
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_fid = feat.id()
        if skipped_geometries:
            QMessageBox.warning(
                self, "Delete point",
                f"Could not check {skipped_geometries} feature(s) due to geometry errors. "
                "No point has been deleted. Repair the geometries and retry."
            )
            return
        # Manual layer is EPSG:4326 by default; 0.0005° is roughly 55 m.
        tol = 0.0005 if target_crs.isGeographic() else max(10.0, self.iface.mapCanvas().mapUnitsPerPixel() * 12.0)
        if best_fid is None or best_dist is None or best_dist > tol:
            QMessageBox.information(self, "Added points", "No user point was found close enough to the click.")
            return
        reply = QMessageBox.question(
            self,
            "Delete point",
            "Delete the user point closest to the click?",
            _messagebox_yes() | _messagebox_no(),
            _messagebox_no(),
        )
        if reply != _messagebox_yes():
            return
        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        ok = layer.deleteFeature(best_fid)
        if not was_editing:
            layer.commitChanges()
        layer.updateExtents()
        layer.triggerRepaint()
        if ok:
            self.refresh_calc_layers(apply_defaults=False)
            self._log(f"Punto propio eliminado: feature id {best_fid}")
        else:
            QMessageBox.warning(self, "Added points", "QGIS could not delete the selected point.")

    def stop_manual_point_tool(self):
        if self.previous_map_tool is not None:
            self.iface.mapCanvas().setMapTool(self.previous_map_tool)
        self.manual_tool = None
        self._log("Point-adding mode finished.")

    def _manual_point_clicked(self, point, button):
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        dialog = ManualFeatureDialog(self, self.iucn_sci_name.text().strip() or self.scientific_name.text().strip(),
                                     map_point=point, map_crs=canvas_crs)
        self._save_manual_point(dialog)

    def add_manual_point_by_coordinates(self):
        dialog = ManualFeatureDialog(self, self.iucn_sci_name.text().strip() or self.scientific_name.text().strip(),
                                     show_coordinates=True)
        self._save_manual_point(dialog)

    def _save_manual_point(self, dialog):
        if _dialog_exec(dialog) != _dialog_accepted():
            return
        try:
            point = dialog.point_in_selected_crs()
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            if dialog.point_crs != wgs84:
                point = QgsCoordinateTransform(dialog.point_crs, wgs84, QgsProject.instance()).transform(point)
            if not (-180 <= point.x() <= 180 and -90 <= point.y() <= 90):
                raise ValueError("The point is outside the valid WGS 84 coordinate bounds.")
            layer = self._ensure_manual_layer()
            if not add_manual_feature(layer, point, wgs84, dialog.values()):
                raise RuntimeError("The point could not be saved.")
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Added points", str(exc))
            return
        self.refresh_calc_layers(apply_defaults=False)
        for index in range(self.calc_layers_list.count()):
            item = self.calc_layers_list.item(index)
            if item.data(_qt_user_role()) == layer.id():
                item.setCheckState(_qt_checked())
                break
        self._update_calc_selection_summary()
        self._log("Point saved. The manual layer is checked in tab 3.")

    def import_manual_points_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import point CSV", "", "CSV (*.csv);;All files (*.*)")
        if not path:
            return
        # Never import a CSV into the layer for points added manually.
        name = os.path.splitext(os.path.basename(path))[0].strip() or "imported_csv_points"
        layer = create_manual_layer(f"CSV: {name}")
        if not _layer_is_usable(layer):
            QMessageBox.warning(self, "Import CSV", "A valid independent CSV layer could not be created.")
            return
        try:
            count = import_manual_csv(
                layer, path, default_scientific_name=self.scientific_name.text().strip(),
                default_include=True, default_review="accepted",
            )
            if count == 0:
                raise ValueError("The CSV did not contain any valid latitude/longitude pairs.")
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            QMessageBox.critical(self, "Error importing CSV", str(exc))
            self._log(f"ERROR CSV: {exc}")
            return
        layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "imported_csv")
        layer.setCustomProperty("aoo_eoo_gbif_pro_import_source", path)
        QgsProject.instance().addMapLayer(layer)
        self.refresh_calc_layers(apply_defaults=False)
        self._log(f"Independent CSV layer imported: {_layer_name(layer)} ({count} points). Selected in tab 3.")
        try:
            self.iface.setActiveLayer(layer)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self._log(f"CSV layer imported, but QGIS could not activate it: {exc}")

    def import_point_shapefile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import point shapefile",
            "",
            "Shapefile (*.shp);;GeoPackage (*.gpkg);;GeoJSON (*.geojson *.json);;Todos los archivos (*.*)",
        )
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0] or "puntos_importados"
        layer = QgsVectorLayer(path, name, "ogr")
        if not _layer_is_usable(layer):
            QMessageBox.critical(self, "Import shapefile", "The selected vector layer could not be opened.")
            self._log(f"ERROR shapefile: could not open {path}")
            return
        if not self._is_probably_point_layer(layer):
            QMessageBox.warning(
                self,
                "Import point layer",
                "The selected layer is not a point layer. Only point or multipoint vector layers can be imported.",
            )
            return
        try:
            if layer.featureCount() == 0:
                QMessageBox.warning(self, "Import shapefile", "The selected layer does not contain points.")
                return
        except (RuntimeError, ValueError, TypeError) as exc:
            self._log(f"ERROR reading imported layer feature count: {exc}")
            QMessageBox.warning(self, "Import shapefile", f"Cannot verify the point count: {exc}")
            return
        layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "imported_point_file")
        layer.setCustomProperty("aoo_eoo_gbif_pro_import_source", path)
        QgsProject.instance().addMapLayer(layer)
        try:
            self.iface.setActiveLayer(layer)
        except (AttributeError, RuntimeError, TypeError) as exc:
            # The layer is already loaded; activation is a UI convenience.
            self._log(f"Imported layer loaded, but QGIS could not activate it: {exc}")
        self.refresh_calc_layers(apply_defaults=False)
        self._log(f"Point shapefile/vector layer imported: {_layer_name(layer)} ({layer.featureCount()} records). Selected in tab 3.")
        try:
            self.iface.messageBar().pushSuccess("Import shapefile", f"Point layer imported: {_layer_name(layer)}")
        except (AttributeError, RuntimeError, TypeError) as exc:
            # Nonessential UI notification; the import and log already succeeded.
            self._log(f"QGIS could not display the import success notification: {exc}")

    def save_manual_csv_template(self):
        default_name = "IUCN_Red_List_calculator_occurrence_template.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save occurrence CSV template", default_name, "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        header = [
            "scientificName", "decimalLatitude", "decimalLongitude", "eventDate",
            "data_citation", "data_origin", "data_curator", "evidence", "identifier",
            "coordinateUncertaintyInMeters", "review_status", "include_for_aoo_eoo", "notes"
        ]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                handle.write(",".join(header) + "\n")
            self._log(f"CSV template saved: {path}")
            try:
                self.iface.messageBar().pushSuccess("CSV template", "Empty CSV template saved.")
            except (AttributeError, RuntimeError, TypeError) as exc:
                # Saving succeeded; only the optional QGIS message bar failed.
                self._log(f"QGIS could not display the CSV success notification: {exc}")
        except OSError as exc:
            QMessageBox.critical(self, "CSV template save error", str(exc))
            self._log(f"ERROR saving CSV template: {exc}")


    # ----------------------------------------------------------- Point Distribution CSV
    def _ensure_last_result(self):
        if self.last_result is None:
            QMessageBox.warning(self, "Point Distribution", "First calculate AOO/EOO. The CSV is generated from the points used in that calculation.")
            return None
        return self.last_result

    def _make_geojson_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        help_label = QLabel(
            "Select the generated layers and tables to export. Each item is saved as its own GeoJSON file. "
            "Geometry is exported in WGS84."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.geojson_layers = QListWidget()
        self.geojson_layers.setToolTip(
            "EN: Tick the plugin-generated outputs you want to export.\n"
            "ES: Marca las salidas generadas por el complemento que quieras exportar."
        )
        layout.addWidget(self.geojson_layers, 1)
        actions = QHBoxLayout()
        for label, state, tip in (
            ("Select all", _qt_checked(), "EN: Select all generated outputs.\nES: Selecciona todas las salidas."),
            ("Clear selection", _qt_unchecked(), "EN: Clear all checks.\nES: Desmarca todas las salidas."),
        ):
            button = QPushButton(label)
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked=False, state=state: self._set_geojson_checks(state))
            actions.addWidget(button)
        refresh = QPushButton("Refresh list")
        refresh.setToolTip("EN: Refresh the list from the project.\nES: Actualiza la lista de salidas del proyecto.")
        refresh.clicked.connect(self._refresh_geojson_layers)
        actions.addWidget(refresh)
        self.export_geojson_button = QPushButton("Export selected as GeoJSON...")
        self.export_geojson_button.setToolTip(
            "EN: Choose a folder and save one GeoJSON per checked item.\n"
            "ES: Elige una carpeta y guarda un GeoJSON por cada elemento marcado."
        )
        self.export_geojson_button.clicked.connect(self.export_project_geojson)
        actions.addWidget(self.export_geojson_button)
        layout.addLayout(actions)
        return tab

    def _set_geojson_checks(self, state):
        for index in range(self.geojson_layers.count()):
            self.geojson_layers.item(index).setCheckState(state)

    def _refresh_geojson_if_visible(self, index):
        if self.tabs.widget(index) is self.geojson_tab:
            self._refresh_geojson_layers()

    def _refresh_geojson_layers(self):
        project = QgsProject.instance()
        previous = {self.geojson_layers.item(i).data(_qt_user_role()): self.geojson_layers.item(i).checkState()
                    for i in range(self.geojson_layers.count())}
        self.geojson_layers.clear()
        seen = set()
        for node in project.layerTreeRoot().findLayers():
            layer = node.layer()
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid() or node.layerId() in seen:
                continue
            seen.add(node.layerId())
            kind = layer.customProperty("aoo_eoo_gbif_pro_layer_type")
            legacy_range = (layer.customProperty("iucn_range_warning")
                            and not layer.name().startswith("PREVIEW"))
            generated = (kind in ("gbif_points", "manual_points", "imported_csv", "point_distribution_output",
                                  "calculation_output")
                         or layer.customProperty("iucn_generated_metric") in ("aoo", "eoo", "report")
                         or layer.customProperty("iucn_geojson_output")
                         or legacy_range)
            if not generated:
                continue
            item = QListWidgetItem(layer.name())
            item.setFlags(item.flags() | _qt_item_user_checkable())
            item.setData(_qt_user_role(), layer.id())
            item.setCheckState(previous.get(layer.id(), _qt_unchecked()))
            self.geojson_layers.addItem(item)

    def export_project_geojson(self):
        self._refresh_geojson_layers()
        project = QgsProject.instance()
        selected = [project.mapLayer(self.geojson_layers.item(i).data(_qt_user_role()))
                    for i in range(self.geojson_layers.count())
                    if self.geojson_layers.item(i).checkState() == _qt_checked()]
        if not selected:
            QMessageBox.information(self, "GeoJSON", "Select at least one generated layer or table.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Select GeoJSON export folder")
        if not folder:
            return
        outputs, errors = write_geojson_layers(selected, folder)
        for path in outputs:
            self._log(f"GeoJSON exported: {path}")
        message = f"Saved {len(outputs)} GeoJSON file(s)."
        if errors:
            for error in errors:
                self._log(f"GeoJSON export error: {error}")
            QMessageBox.warning(self, "GeoJSON", message + "\n\n" + "\n".join(errors[:10]))
        else:
            self.iface.messageBar().pushSuccess("GeoJSON", message)

    def _choose_point_output_crs(self):
        selector = QgsProjectionSelectionDialog(self)
        selector.setCrs(self.point_output_crs)
        if _dialog_exec(selector) != _dialog_accepted():
            return
        crs = selector.crs()
        if not crs.isValid():
            QMessageBox.warning(self, "Point Distribution", "Select a valid coordinate reference system.")
            return
        self.point_output_crs = crs
        self.point_output_crs_button.setText(f"Change layer CRS ({crs.authid() or crs.description()})")

    def _point_distribution_settings(self):
        defaults = self.last_result.get("iucn_polygon_attrs") or {}
        dialog = PointDistributionSettingsDialog(
            self, default_name=defaults.get("sci_name") or self.last_result.get("taxon_name", ""),
            default_subspecies=defaults.get("subspecies", ""), defaults=defaults,
        )
        if _dialog_exec(dialog) == _dialog_accepted():
            settings = dialog.values()
            settings["output_crs"] = self.point_output_crs
            return settings
        return None

    def create_iucn_polygon_field_guide(self):
        _dialog_exec(PointDistributionHelpDialog(self, polygon=True))

    def create_point_distribution_table(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        try:
            layer = create_point_distribution_layer(result, settings)
            layer.setCustomProperty("iucn_geojson_output", True)
            QgsProject.instance().addMapLayer(layer)
            self.point_distribution_layer = layer
            self.iface.showAttributeTable(layer)
            self._log(f"Point Distribution table added to the project: {layer.featureCount()} rows.")
            self.iface.messageBar().pushSuccess("Point Distribution", "Point Distribution table added to the QGIS project.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR Point Distribution: {exc}")

    def save_point_distribution_csv(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Point Distribution CSV", "point_distribution.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            count = write_point_distribution_csv(result, settings, path)
            self._log(f"CSV Point Distribution guardado: {path} ({count} filas)")
            self.iface.messageBar().pushSuccess("Point Distribution", f"CSV guardado con {count} filas.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR saving Point Distribution CSV: {exc}")

    def create_point_distribution_shapefile_layer(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        try:
            layer = create_point_distribution_shapefile_layer(result, settings)
            self._open_point_distribution_layer(layer)
            self._log(f"Point Distribution layer added to the project: {layer.featureCount()} points.")
            self.iface.messageBar().pushSuccess("Point Distribution", "Point Distribution layer added to the QGIS project.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR Point Distribution layer: {exc}")

    def _open_point_distribution_layer(self, layer):
        layer.setCustomProperty("aoo_eoo_gbif_pro_layer_type", "point_distribution_output")
        QgsProject.instance().addMapLayer(layer)
        self.iface.showAttributeTable(layer)

    def save_point_distribution_shapefile(self):
        result = self._ensure_last_result()
        if result is None:
            return
        settings = self._point_distribution_settings()
        if settings is None:
            return
        QMessageBox.information(
            self, "SRedList scientific name",
            "EN: SRedList accepts a binomial scientific name only (Genus species).\n"
            "ES: SRedList solo admite un nombre cient\u00edfico binomial (G\u00e9nero especie).",
        )
        path, _ = QFileDialog.getSaveFileName(self, "Save Point Distribution shapefile", "point_distribution.shp", "Shapefile (*.shp)")
        if not path:
            return
        if not path.lower().endswith(".shp"):
            path += ".shp"
        try:
            count = write_point_distribution_shapefile(result, settings, path)
            self._log(f"Point Distribution shapefile saved: {path} ({count} points)")
            layer = QgsVectorLayer(path, os.path.splitext(os.path.basename(path))[0], "ogr")
            if layer.isValid():
                self._open_point_distribution_layer(layer)
            else:
                QMessageBox.warning(self, "Point Distribution", "The shapefile was saved but could not be opened in QGIS.")
            self.iface.messageBar().pushSuccess("Point Distribution", f"Shapefile saved with {count} points.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Point Distribution", str(exc))
            self._log(f"ERROR saving Point Distribution shapefile: {exc}")

    # ----------------------------------------------------------- GBIF DOI
    def _gbif_ids_from_result(self, result):
        ids = []
        seen = set()
        manual_or_non_gbif = 0
        missing_gbif_id = 0
        for rec in (result or {}).get("used_records", []):
            origin = (rec.get("data_origin") or rec.get("origin") or "").strip().upper()
            gbif_id = str(rec.get("gbifID") or "").strip()
            if gbif_id:
                if gbif_id not in seen:
                    ids.append(gbif_id)
                    seen.add(gbif_id)
            else:
                if origin == "GBIF":
                    missing_gbif_id += 1
                else:
                    manual_or_non_gbif += 1
        return ids, manual_or_non_gbif, missing_gbif_id

    def _gbif_ids_for_download(self):
        result = self._ensure_last_result()
        if result is None:
            return None
        ids, manual_count, missing_count = self._gbif_ids_from_result(result)
        if not ids:
            QMessageBox.warning(
                self,
                "GBIF citation",
                "There are no gbifIDs in the points used. An official GBIF DOI can only be generated for GBIF records with gbifID."
            )
            return None
        return ids, manual_count, missing_count

    def _gbif_ids_preview_text(self, result):
        ids, manual_count, missing_count = self._gbif_ids_from_result(result)
        preview_ids = "\n".join(ids[:250])
        if len(ids) > 250:
            preview_ids += f"\n... ({len(ids) - 250} gbifID más)"
        return (
            f"Registros GBIF con gbifID usados en el cálculo: {len(ids)}\n"
            f"Puntos propios/no GBIF usados: {manual_count}\n"
            f"Registros GBIF usados sin gbifID: {missing_count}\n\n"
            "Lista gbifID que se enviará a GBIF para crear la descarga oficial:\n"
            f"{preview_ids if preview_ids else '[sin gbifID]'}\n\n"
            "You do not need to paste this list into any website if you use the ‘Request official download and DOI’ button. "
            "The plugin will send it to GBIF through the download API. Copying to the clipboard is only for review or archiving."
        )

    def _refresh_gbif_doi_tab(self):
        if self.last_result is not None and hasattr(self, "gbif_download_result"):
            self.gbif_download_result.setPlainText(self._gbif_ids_preview_text(self.last_result))

    def prepare_gbif_download_ids(self):
        result = self._ensure_last_result()
        if result is None:
            return
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        self.gbif_download_result.setPlainText(self._gbif_ids_preview_text(result))
        ids, manual_count, missing_count = ids_info
        self._log(f"Prepared {len(ids)} gbifIDs for the official GBIF download. Non-GBIF points: {manual_count}; GBIF without gbifID: {missing_count}.")
        self.iface.messageBar().pushSuccess("GBIF citation", f"Prepared {len(ids)} gbifIDs to request an official DOI from GBIF.")

    def copy_gbif_ids(self):
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        ids, _, _ = ids_info
        QApplication.clipboard().setText("\n".join(ids))
        self._log("Used gbifIDs copied to the clipboard.")
        self.iface.messageBar().pushSuccess("GBIF citation", "gbifIDs copied to clipboard.")

    def request_gbif_occurrence_download(self):
        ids_info = self._gbif_ids_for_download()
        if ids_info is None:
            return
        ids, manual_count, missing_count = ids_info
        username = self.gbif_download_user.text().strip()
        password = self.gbif_download_password.text()
        email = self.gbif_download_email.text().strip()
        fmt = self.gbif_download_format.currentData() or "SIMPLE_CSV"
        missing = []
        if not username:
            missing.append("GBIF username")
        if not password:
            missing.append("GBIF password")
        if missing:
            QMessageBox.warning(self, "GBIF citation", "Missing fields: " + ", ".join(missing))
            return
        if "@" in username:
            QMessageBox.warning(
                self,
                "GBIF citation",
                "Enter your GBIF username, not your email address.\n\n"
                "Example: your_gbif_username\n"
                "The email address should be entered only in ‘Notification email’."
            )
            return

        if manual_count or missing_count:
            note = (
                f"An official DOI will be requested only for {len(ids)} GBIF records with gbifID.\n"
                f"Manual or non-GBIF points used: {manual_count}.\n"
                f"GBIF records without gbifID: {missing_count}.\n\n"
                "Those points will not be covered by the GBIF DOI. Continue?"
            )
            confirm = QMessageBox.question(self, "GBIF citation", note)
            try:
                yes_value = QMessageBox.Yes
            except AttributeError:
                yes_value = QMessageBox.StandardButton.Yes
            if confirm != yes_value:
                return

        try:
            key = request_occurrence_download_by_gbif_ids(
                ids,
                username=username,
                password=password,
                notification_email=email or None,
                download_format=fmt,
            )
            self.gbif_download_key = key
            self.gbif_download_key_edit.setText(key)
            self.gbif_download_result.setPlainText(
                "Request sent to GBIF.\n\n"
                f"Download key: {key}\n"
                f"GBIF records requested: {len(ids)}\n"
                f"Format: {fmt}\n\n"
                "The DOI may not yet exist. Press ‘Check status / DOI’ again in a few minutes. "
                "GBIF will also send an email if you provided a notification address."
            )
            self._log(f"Official GBIF download requested. Key: {key}")
            self.iface.messageBar().pushSuccess("GBIF citation", f"Request submitted. GBIF key: {key}")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "GBIF citation", str(exc))
            self._log(f"ERROR requesting GBIF download: {exc}")

    def _citation_from_gbif_download(self, response: dict) -> str:
        citation = (response or {}).get("citation") or ""
        if citation:
            return citation
        doi = (response or {}).get("doi") or ""
        if doi:
            doi_text = str(doi).strip()
            doi_url = doi_text if doi_text.startswith("http") else f"https://doi.org/{doi_text}"
            year = datetime.now().year
            return f"GBIF.org ({year}). GBIF Occurrence Download. {doi_url}"
        return ""

    def check_gbif_occurrence_download(self):
        key = self.gbif_download_key_edit.text().strip() or self.gbif_download_key
        if not key:
            QMessageBox.warning(self, "GBIF citation", "Enter or request a GBIF download key first.")
            return
        try:
            response = get_occurrence_download(key)
            self.gbif_download_key = key
            self.gbif_download_response = response
            status = response.get("status", "")
            doi = response.get("doi", "")
            citation = self._citation_from_gbif_download(response)
            download_link = response.get("downloadLink") or response.get("downloadUrl") or ""
            if doi:
                doi_text = str(doi).strip()
                doi_url = doi_text if doi_text.startswith("http") else f"https://doi.org/{doi_text}"
            else:
                doi_url = "[not yet available]"
            result_text = (
                "GBIF download status\n\n"
                f"Key: {key}\n"
                f"Status: {status}\n"
                f"DOI: {doi_url}\n"
                f"Records in download: {response.get('numberRecords', '')}\n"
                f"Download link: {download_link}\n\n"
                "Recommended citation:\n"
                f"{citation if citation else '[not available yet; check again when status is SUCCEEDED]'}\n\n"
                "Remember: this citation covers only the GBIF records included in the official download."
            )
            self.gbif_download_result.setPlainText(result_text)
            if status == "SUCCEEDED" or doi:
                layer = create_gbif_occurrence_download_result_layer(response)
                layer.setCustomProperty("iucn_geojson_output", True)
                QgsProject.instance().addMapLayer(layer)
                self.gbif_doi_layer = layer
                self.iface.messageBar().pushSuccess("GBIF citation", "GBIF DOI ready and table added to the project.")
            else:
                self.iface.messageBar().pushMessage("GBIF citation", f"Current status: {status}", level=Qgis.Info, duration=6)
            self._log(f"GBIF download status {key}: {status}; DOI: {doi}")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "GBIF citation", str(exc))
            self._log(f"ERROR checking GBIF download: {exc}")

    def copy_gbif_citation(self):
        text = self.gbif_download_result.toPlainText() if hasattr(self, "gbif_download_result") else ""
        citation = ""
        if self.gbif_download_response:
            citation = self._citation_from_gbif_download(self.gbif_download_response)
        if not citation and "Recommended citation:" in text:
            citation = text.split("Recommended citation:", 1)[1].strip().split("\n\n", 1)[0].strip()
        if not citation or citation.startswith("["):
            QMessageBox.warning(self, "GBIF citation", "There is no citation available yet. Check the status until GBIF returns the DOI.")
            return
        QApplication.clipboard().setText(citation)
        self.iface.messageBar().pushSuccess("GBIF citation", "GBIF citation copied to clipboard.")
        self._log("GBIF citation copied to clipboard.")

    def _iucn_polygon_attrs(self) -> dict:
        return {
            "sci_name": self.iucn_sci_name.text().strip() or self.scientific_name.text().strip(),
            "presence": self.iucn_presence.currentData(),
            "origin": self.iucn_origin.currentData(),
            "seasonal": self.iucn_seasonal.currentData(),
            "compiler": self.iucn_compiler.text().strip(),
            "yrcompiled": self.iucn_yrcompiled.value(),
            "citation": self.iucn_citation.text().strip(),
            "subspecies": self.iucn_subspecies.text().strip() or (self.infraspecific_epithet.text().strip() if self.assess_infraspecific.isChecked() else ""),
            "subpop": self.iucn_subpop.text().strip(),
            "data_sens": self.iucn_data_sens.currentData(),
            "sens_comm": self.iucn_sens_comm.text().strip(),
        }

    # --------------------------------------------------------------- calculate

    def _analysis_crs_authid(self) -> str:
        """Resolve a preset or user-specified EPSG code, avoiding stale combo data."""
        raw_text = self.analysis_crs.currentText().strip()
        index = self.analysis_crs.currentIndex()
        if index >= 0 and raw_text == self.analysis_crs.itemText(index):
            data = self.analysis_crs.itemData(index)
            if data:
                return str(data).strip()
        match = re.search(r"EPSG\s*[:=]\s*(\d+)", raw_text, flags=re.IGNORECASE)
        if match:
            return f"EPSG:{match.group(1)}"
        if raw_text.isdigit():
            return f"EPSG:{raw_text}"
        return raw_text

    def _choose_analysis_crs(self):
        """Choose any QGIS CRS via QGIS' native CRS browser."""
        selector = QgsProjectionSelectionDialog(self)
        current = QgsCoordinateReferenceSystem(self._analysis_crs_authid())
        if current.isValid():
            selector.setCrs(current)
        if _dialog_exec(selector) != _dialog_accepted():
            return
        selected = selector.crs()
        if not selected.isValid():
            QMessageBox.warning(self, "CRS", "Choose a valid CRS.")
            return
        authid = selected.authid()
        if not authid:
            QMessageBox.warning(
                self, "CRS",
                "This CRS has no authority identifier. Please choose a CRS with an EPSG code."
            )
            return
        index = self.analysis_crs.findData(authid)
        if index >= 0:
            self.analysis_crs.setCurrentIndex(index)
        else:
            # An ad-hoc entry has item data too, so future selection stays stable.
            self.analysis_crs.addItem(f"{selected.description()} — {authid}", authid)
            self.analysis_crs.setCurrentIndex(self.analysis_crs.count() - 1)

    def _remove_range_preview(self):
        preview_id, self.range_preview_id = self.range_preview_id, None
        project = QgsProject.instance()
        if preview_id and project.mapLayer(preview_id):
            project.removeMapLayer(preview_id)

    def generate_distribution_range(self, preview=False):
        """Make a separate editable, expert-reviewable range from the last calculation."""
        if not self.last_result or not self.last_result.get("used_records"):
            QMessageBox.warning(
                self, "Distribution range",
                "Calculate AOO/EOO first. The range uses the records retained by that calculation."
            )
            return
        try:
            mode = self.range_mode.currentData()
            if mode not in ("separate", "merge"):
                QMessageBox.warning(
                    self, "Distribution range",
                    "Choose whether to keep disjunct occurrence groups separate or connect them."
                )
                return
            polygon_layer, diagnostics = create_distribution_range_layer(
                self.last_result,
                mode=mode,
                grouping_distance_m=self._range_distance_value(self.range_group_distance),
                concavity=self.range_concavity.value(),
                smoothing=self.range_smoothing.value(),
                buffer_m=self._range_distance_value(self.range_buffer),
                iucn_attrs=self.last_result["iucn_polygon_attrs"],
                generalised=0,
                tip_rounding_radius_m=self._range_distance_value(self.range_tip_radius) if self.range_round_tips.isChecked() else 0,
            )
            self._remove_range_preview()
            if preview:
                polygon_layer.setName("PREVIEW - distribution range")
                polygon_layer.setOpacity(0.55)
                self.range_preview_id = polygon_layer.id()
            QgsProject.instance().addMapLayer(polygon_layer)
            self._log(
                f"Distribution range: {polygon_layer.featureCount()} polygon(s); "
                f"mode={mode}; grouping_distance_m={self._range_distance_value(self.range_group_distance):g}; "
                f"concavity={self.range_concavity.value():g}; smoothing={self.range_smoothing.value()}; "
                f"buffer_m={self._range_distance_value(self.range_buffer):g}."
            )
            for warning in diagnostics:
                self._log(f"Distribution range note: {warning}")
            QMessageBox.information(
                self, "Distribution range",
                ("Temporary preview layer added to the map." if preview else
                 "A preliminary distribution polygon has been created. Review its limits before using it in an assessment.")
                + ("\n\n" + "\n".join(diagnostics[:5]) if diagnostics else "")
            )
        except (ValueError, RuntimeError, TypeError, AttributeError) as exc:
            QMessageBox.critical(self, "Distribution range error", str(exc))
            self._log(f"Distribution range error: {exc}")

    def calculate(self):
        self.refresh_calc_layers(apply_defaults=False)
        layers = self._selected_calc_layers()

        if not layers:
            QMessageBox.warning(self, "Calculation", "Check one or more point layers in the list in tab 3 before calculating.")
            return

        attrs = self._iucn_polygon_attrs()
        required = ["sci_name", "compiler", "citation"]
        if self.assess_infraspecific.isChecked():
            required.append("subspecies")
        if attrs["data_sens"] == 1:
            required.append("sens_comm")
        missing = [field for field in required if not attrs[field]]
        if missing:
            QMessageBox.warning(self, "Required IUCN attributes",
                                "Complete these fields before calculating: " + ", ".join(missing))
            getattr(self, "iucn_" + missing[0]).setFocus()
            return

        layer_description = "; ".join(
            f"{_layer_name(layer)} ({layer.featureCount()} records)" for layer in layers
        )
        if len(layers) > 1:
            # Both buttons exist in QGIS 3 (Qt5) and QGIS 4 (Qt6).
            yes = getattr(QMessageBox, "Yes", None)
            no = getattr(QMessageBox, "No", None)
            if yes is None:
                yes = QMessageBox.StandardButton.Yes
                no = QMessageBox.StandardButton.No
            reply = QMessageBox.question(
                self, "Confirm combined layers",
                "The following layers will be COMBINED for this calculation:\n"
                f"{layer_description}\n\n"
                "Are all these layers intended inputs?",
                yes | no, no,
            )
            if reply != yes:
                self._log("Combined-layer calculation cancelled; the selected layers were not changed.")
                return
        if abs(self.cell_size.value() - 2000) > 0.001:
            yes = getattr(QMessageBox, "Yes", None)
            no = getattr(QMessageBox, "No", None)
            if yes is None:
                yes = QMessageBox.StandardButton.Yes
                no = QMessageBox.StandardButton.No
            reply = QMessageBox.question(
                self, "Nonstandard AOO grid",
                f"AOO cell size: {self.cell_size.value():g} m. "
                "The IUCN reference size is 2000 m (2 × 2 km).\n"
                "Continue with this custom cell size?",
                yes | no, no,
            )
            if reply != yes:
                self._log("Calculation cancelled to review the AOO grid size.")
                return
        self._log("Layers sent to the calculation: " + layer_description)
        max_uncert = self.max_uncertainty.value() if self.use_uncertainty_filter.isChecked() else None
        try:
            result = run_aoo_eoo(
                layers,
                analysis_crs_authid=self._analysis_crs_authid(),
                cell_size_m=self.cell_size.value(),
                max_uncertainty_m=max_uncert,
                include_pending_manual=self.include_pending.isChecked(),
                deduplicate=self.deduplicate.isChecked(),
                iucn_polygon_attrs=attrs,
                iucn_b_inputs=self._iucn_criterion_b_inputs(),
            )
            result["taxon_name"] = attrs["sci_name"]
            result["taxon_key"] = self.taxon_key.text().strip()
            try:
                result["gbif_query_params"] = self._build_gbif_params()
            except Exception:
                result["gbif_query_params"] = {}
            self.last_result = result
            self._refresh_gbif_doi_tab()
            project = QgsProject.instance()
            for layer in create_report_layers(result).values():
                layer.setCustomProperty("iucn_generated_metric", "report")
                project.addMapLayer(layer)
            root = project.layerTreeRoot()
            input_ids = {layer.id() for layer in layers}
            input_nodes = [node for node in root.findLayers() if node.layerId() in input_ids]
            parent = input_nodes[-1].parent() if input_nodes else root
            index = parent.children().index(input_nodes[-1]) + 1 if input_nodes else 0
            for metric in ("aoo", "eoo"):
                output = result[f"{metric}_layer"]
                if output is not None:
                    output.setCustomProperty("iucn_generated_metric", metric)
                    project.addMapLayer(output, False)
                    parent.insertLayer(index, output)
                    index += 1
            self._log("Calculation finished. Layers and tables added to the QGIS project.")
            self._log(f"  Used records: {result['n_used']}")
            self._log(f"  Excluded records: {result['n_excluded']}")
            self._log(f"  Occupied AOO cells: {result['n_cells']}")
            self._log(f"  AOO: {result['aoo_km2']:.2f} km²")
            self._log(f"  EOO: {result['eoo_km2']:.2f} km²")
            iucn_b = result.get("iucn_criterion_b", {})
            if iucn_b:
                self._log(f"  Indicative category by AOO: {iucn_b.get('aoo_category', 'Not evaluable')}")
                self._log(f"  Indicative category by EOO: {iucn_b.get('eoo_category', 'Not evaluable')}")
            self._log("  Table added: AOO_EOO report summary")
            self._log("  Tab 6 updated with the gbifIDs used to request the official GBIF DOI")
            self._log("  Table added: AOO_EOO unused records")
            self.iface.messageBar().pushSuccess("AOO/EOO", "Calculation finished. The final layers and report tables are in the Layers panel.")
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "AOO/EOO calculation error", str(exc))
            self._log(f"ERROR calculation: {exc}")
