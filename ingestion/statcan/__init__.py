"""Ingestion of the Statistics Canada census sources.

Four responsibilities, four modules, same split as the three ingestion
packages that came before:

    datasets.py   the catalogue -- what is fetched, from where, under which
                  licence, and what it is expected to contain. No I/O.
    download.py   HTTP only. Knows nothing about the database.
    parse.py      bytes in, records out. Knows nothing about HTTP or the
                  database.
    run.py        orchestration, the pipeline journal, and the transaction.
"""
