"""SQLite unit of work. Acquire the writer lock before checking stock or idempotency."""

from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("DATA_DIR", ROOT / "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    "sqlite:///" + str(DATA / "store.db"), connect_args={"timeout": 20}
)
IST = timezone(timedelta(hours=5, minutes=30))


def now():
    return datetime.now(IST).isoformat(timespec="seconds")


@contextmanager
def tx():
    with engine.connect() as c:
        c.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise


def run(c, sql, **args):
    return c.execute(text(sql), args)


def rows(c, sql, **args):
    return [dict(r) for r in run(c, sql, **args).mappings()]


def one(c, sql, **args):
    return next(iter(rows(c, sql, **args)), None)


def audit(c, who, step, detail, job=None):
    run(
        c,
        "insert into audit(at,actor,step,detail,job) values (:at,:who,:step,:detail,:job)",
        at=now(),
        who=who,
        step=step,
        detail=str(detail)[:1500],
        job=job,
    )


DDL = """
create table if not exists chats(id integer primary key, name text not null, token text unique not null);
create table if not exists messages(id integer primary key,chat integer not null,side text not null,body text not null,at text not null,job integer,record integer,nonce text,unique(chat,side,nonce));
create table if not exists chat_seen(chat integer, side text, last_id integer, primary key(chat,side));
create table if not exists chat_media(message integer primary key, hash text not null);
create index if not exists messages_thread on messages(chat,id);
create table if not exists text_queue(message integer primary key,status text default 'queued');
create table if not exists receipt_links(payment integer primary key, order_id integer not null, chat integer not null);
create table if not exists receipt_chats(payment integer primary key,chat integer not null);
create table if not exists confirmations(key text primary key,result text);
create table if not exists users(name text primary key, role text not null, digest text not null);
create table if not exists sessions(token text primary key, name text, expires integer);
create table if not exists products(id integer primary key,name text collate nocase unique,unit text,buy integer,sell integer,stock real,reserved real default 0,threshold real,active integer default 1);
create table if not exists records(id integer primary key,kind text,ref text collate nocase,party text collate nocase,amount integer,status text,items text,at text,fulfilled_at text, unique(kind,ref));
create table if not exists movements(id integer primary key,at text,product text,delta real,reservation real,reason text);
create table if not exists jobs(id integer primary key,hash text,name text,source text,actor text,role text,status text,reason text default '',payload text default '{}',at text);
create index if not exists job_hash on jobs(hash);
create table if not exists audit(id integer primary key,at text,actor text,step text,detail text,job integer);
create table if not exists settings(id integer primary key check(id=1),invoice_limit integer);
insert or ignore into settings values(1,500000);
"""


def init():
    with tx() as c:
        for statement in DDL.split(";"):
            if statement.strip():
                c.exec_driver_sql(statement)
