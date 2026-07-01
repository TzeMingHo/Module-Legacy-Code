import datetime

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data.connection import db_cursor
from data.users import User


@dataclass
class Bloom:
    id: int
    sender: User
    content: str
    sent_timestamp: datetime.datetime

@dataclass
class RebloomView:
    id: int
    sender: str
    content: str
    sent_timestamp: datetime.datetime
    rebloomer: str
    activity_timestamp: datetime.datetime

def add_bloom(*, sender: User, content: str) -> Bloom:
    hashtags = [word[1:] for word in content.split(" ") if word.startswith("#")]

    now = datetime.datetime.now(tz=datetime.UTC)
    bloom_id = int(now.timestamp() * 1000000)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO blooms (id, sender_id, content, send_timestamp) VALUES (%(bloom_id)s, %(sender_id)s, %(content)s, %(timestamp)s)",
            dict(
                bloom_id=bloom_id,
                sender_id=sender.id,
                content=content,
                timestamp=datetime.datetime.now(datetime.UTC),
            ),
        )
        for hashtag in hashtags:
            cur.execute(
                "INSERT INTO hashtags (hashtag, bloom_id) VALUES (%(hashtag)s, %(bloom_id)s)",
                dict(hashtag=hashtag, bloom_id=bloom_id),
            )

def add_rebloom(*, user_id: int, bloom_id: int) -> bool:
    with db_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO reblooms (user_id, bloom_id) VALUES (%(user_id)s, %(bloom_id)s) ON CONFLICT (user_id, bloom_id) DO NOTHING", dict(user_id=user_id, bloom_id=bloom_id)
            )
            return True
        except Exception as e:
            print(f"cannot rebloom bloom: {bloom_id}")
            return False


def get_blooms_for_user(
    username: str, *, before: Optional[int] = None, limit: Optional[int] = None
) -> List[Bloom]:
    with db_cursor() as cur:
        kwargs = {
            "sender_username": username,
        }
        if before is not None:
            before_clause = "AND send_timestamp < %(before_limit)s"
            kwargs["before_limit"] = before
        else:
            before_clause = ""

        limit_clause = make_limit_clause(limit, kwargs)

        cur.execute(
            f"""SELECT
              blooms.id, users.username, content, send_timestamp
            FROM
              blooms INNER JOIN users ON users.id = blooms.sender_id
            WHERE
              username = %(sender_username)s
              {before_clause}
            ORDER BY send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms = []
        for row in rows:
            bloom_id, sender_username, content, timestamp = row
            blooms.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                )
            )
    return blooms

def get_reblooms_for_user(username: str, *, before: Optional[int] = None, limit: Optional[int] = None) -> List[Bloom]:
    with db_cursor() as cur:
        kwargs = {
            "username": username,
        }
        if before is not None:
            before_clause = "AND send_timestamp < %(before_limit)s"
            kwargs["before_limit"] = before
        else:
            before_clause = ""

        limit_clause = make_limit_clause(limit, kwargs)

        cur.execute(
            f"""
            SELECT 
                blooms.id, users.username AS sender, blooms.content, blooms.send_timestamp, rebloomer.username AS rebloomer, reblooms.rebloom_timestamp AS activity_time
            FROM 
                reblooms 
                INNER JOIN blooms ON blooms.id = reblooms.bloom_id
                INNER JOIN users ON users.id = blooms.sender_id
                INNER JOIN users AS rebloomer ON rebloomer.id = reblooms.user_id
            WHERE
                rebloomer.username = %(username)s
                {before_clause}
            ORDER BY reblooms.rebloom_timestamp DESC
            {limit_clause}
            """,
            kwargs
        )
        rows = cur.fetchall()

        reblooms = []
        for row in rows:
            bloom_id, send_username, content, timestamp, rebloomer_name, activity_time = row
            reblooms.append(
                RebloomView(
                    id=bloom_id,
                    sender=send_username,
                    content=content,
                    sent_timestamp=timestamp,
                    rebloomer=rebloomer_name,
                    activity_timestamp=activity_time
                )
            )
    return reblooms



def get_bloom(bloom_id: int) -> Optional[Bloom]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT blooms.id, users.username, content, send_timestamp FROM blooms INNER JOIN users ON users.id = blooms.sender_id WHERE blooms.id = %s",
            (bloom_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        bloom_id, sender_username, content, timestamp = row
        return Bloom(
            id=bloom_id,
            sender=sender_username,
            content=content,
            sent_timestamp=timestamp,
        )


def get_blooms_with_hashtag(
    hashtag_without_leading_hash: str, *, limit: int = None
) -> List[Bloom]:
    kwargs = {
        "hashtag_without_leading_hash": hashtag_without_leading_hash,
    }
    limit_clause = make_limit_clause(limit, kwargs)
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT
              blooms.id, users.username, content, send_timestamp
            FROM
              blooms INNER JOIN hashtags ON blooms.id = hashtags.bloom_id INNER JOIN users ON blooms.sender_id = users.id
            WHERE
              hashtag = %(hashtag_without_leading_hash)s
            ORDER BY send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms = []
        for row in rows:
            bloom_id, sender_username, content, timestamp = row
            blooms.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                )
            )
    return blooms


def make_limit_clause(limit: Optional[int], kwargs: Dict[Any, Any]) -> str:
    if limit is not None:
        limit_clause = "LIMIT %(limit)s"
        kwargs["limit"] = limit
    else:
        limit_clause = ""
    return limit_clause
