import sqlite3
from flask import  g


def get_db():
    if 'lifemap_db' not in g:
        g.lifemap_db = sqlite3.connect("LifeMap.db")
        g.lifemap_db.row_factory = sqlite3.Row
    return g.lifemap_db