"""Ingestion of the APCIQ *Baromètre résidentiel* quarterly PDF, Montréal edition.

Four modules, one responsibility each, the same split as the other sources:

    editions.py   which quarters exist, and where each PDF lives
    download.py   HTTP only -- fetches and archives PDFs, touches no database
    parse.py      PDF -> observations. Pure: no HTTP, no database, no clock
    load.py       database only -- takes observations, writes rows, never commits
    run.py        orchestration, and the entry in raw.pipeline_run

Attribution required by the source: Source : APCIQ par le système Centris.
"""
