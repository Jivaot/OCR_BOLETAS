"""
Sistema de deduplicación para evitar repetición de datos.
Registra boletas ya procesadas y rechaza duplicados.
"""
import json
from pathlib import Path
from typing import Set

from schema import BoletaTranscrita

from config import DB_TRANSCRIPCIONES


class Deduplicador:
    """Gestiona claves únicas de boletas para prevenir duplicados."""
    
    def __init__(self, db_path: Path = DB_TRANSCRIPCIONES):
        self.db_path = db_path
        self._claves: Set[str] = set()
        self._cargar()
    
    def _cargar(self) -> None:
        """Carga registro existente de transcripciones."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._claves = set(data.get("claves", []))
            except (json.JSONDecodeError, IOError):
                self._claves = set()
    
    def _guardar(self) -> None:
        """Persiste el registro de claves."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({"claves": list(self._claves)}, f, ensure_ascii=False)
    
    def es_duplicado(self, boleta: BoletaTranscrita) -> bool:
        """Retorna True si la boleta ya fue procesada."""
        clave = boleta.clave_unica()
        if not clave or clave == "||":
            return False
        return clave in self._claves
    
    def registrar(self, boleta: BoletaTranscrita) -> None:
        """Registra una boleta como procesada."""
        clave = boleta.clave_unica()
        if clave:
            self._claves.add(clave)
            self._guardar()
    
    def filtrar_duplicados(
        self, boletas: list[BoletaTranscrita], registrar_nuevas: bool = True
    ) -> list[BoletaTranscrita]:
        """
        Filtra boletas duplicadas.
        Si registrar_nuevas=True, registra las que pasan el filtro.
        """
        resultado = []
        for b in boletas:
            if not self.es_duplicado(b):
                resultado.append(b)
                if registrar_nuevas:
                    self.registrar(b)
        return resultado
    
    def limpiar_registro(self) -> None:
        """Limpia todo el registro (útil para reprocesar desde cero)."""
        self._claves = set()
        self._guardar()
