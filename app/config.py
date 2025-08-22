import os

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET", "super-secure")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///data.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rutas de plantillas DOCX
    TEMPLATE_INTERNO   = os.environ.get("TEMPLATE_INTERNO",   "templates_docx/formato interno de proyecto.docx")
    TEMPLATE_BIMESTRAL = os.environ.get("TEMPLATE_BIMESTRAL", "templates_docx/Reporte_Bimestral_Plantilla.docx")
    TEMPLATE_FINAL     = os.environ.get("TEMPLATE_FINAL",     "templates_docx/Reporte_Final_Lleno.docx")
