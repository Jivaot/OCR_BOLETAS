"""
Esquema de datos para boletas transcritas.
Define la estructura y validaciones para evitar datos inconsistentes.
"""
from dataclasses import dataclass, field
import re
from typing import Optional
from datetime import date


@dataclass
class BoletaTranscrita:
    """
    Representa una boleta transcrita con sus campos extraídos.
    Incluye metadatos de confianza y origen.
    """
    fecha_dia: Optional[str] = None
    fecha_mes: Optional[str] = None
    fecha_anio: Optional[str] = None
    numero_reporte: Optional[str] = None
    camion: Optional[str] = None
    patente: Optional[str] = None
    operador: Optional[str] = None
    obra: Optional[str] = None
    tipo_faena: Optional[str] = None
    horarios: Optional[str] = None
    observaciones: Optional[str] = None
    tipo_boleta: Optional[str] = None
    
    imagen_origen: Optional[str] = None
    confianza_promedio: float = 0.0
    
    def fecha_completa(self) -> Optional[str]:
        """Retorna fecha en formato DD/MM/YYYY."""
        if all([self.fecha_dia, self.fecha_mes, self.fecha_anio]):
            return f"{self.fecha_dia.zfill(2)}/{self.fecha_mes.zfill(2)}/20{self.fecha_anio}"
        return None
    
    def clave_unica(self) -> str:
        """
        Genera clave única para deduplicación.
        Combina número de reporte + fecha + patente para detectar duplicados.
        """
        parts = [
            (self.numero_reporte or "").strip(),
            self.fecha_completa() or "",
            self._normalizar_patente(self.patente),
        ]
        return "|".join(parts).lower()
    
    @staticmethod
    def _normalizar_patente(patente: Optional[str]) -> str:
        """Normaliza patente para comparación (quita espacios, puntos, guiones)."""
        if not patente:
            return ""
        return "".join(c for c in patente.upper() if c.isalnum())
    
    def to_dict(self) -> dict:
        """Exporta a diccionario para Excel."""
        return {
            "Fecha": self.fecha_completa() or "",
            "N° Reporte": self.numero_reporte or "",
            "Camión": self.camion or "",
            "Patente": self.patente or "",
            "Operador": self.operador or "",
            "Obra": self.obra or "",
            "Tipo de Faena": self.tipo_faena or "",
            "Horarios": self.horarios or "",
            "Observaciones": self.observaciones or "",
            "Tipo Boleta": self.tipo_boleta or "",
            "Imagen Origen": self.imagen_origen or "",
            "Confianza Promedio": round(self.confianza_promedio, 2),
        }
    
    def es_valida(self) -> bool:
        """Mínimos requeridos para considerar la boleta válida."""
        tiene_reporte = bool(self.numero_reporte and re.fullmatch(r"\d{3,7}", str(self.numero_reporte).strip()))
        tiene_identificador = bool(self.patente and len(self.patente.strip()) >= 5)
        contexto_operacion = any(
            v and len(str(v).strip()) >= 3
            for v in (self.camion, self.obra, self.operador)
        )
        return bool((tiene_reporte or tiene_identificador) and contexto_operacion)
