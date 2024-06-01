from pydantic import BaseModel
from typing import List, Union, Optional
from peewee import *
from playhouse.shortcuts import model_to_dict

import json
import uuid
import time

from apps.web.internal.db import DB

####################
# Thread DB Schema
####################

class Thread(Model):
    id = CharField(unique=True)
    user_id = CharField()
    created_at = BigIntegerField()

    class Meta:
        database = DB


####################
# Chat DB Schema
####################


class Chat(Model):
    id = CharField(unique=True)
    thread_id = CharField(null=True)
    user_id = CharField()
    title = TextField()
    chat = TextField()  # Save Chat JSON as Text

    created_at = BigIntegerField()
    updated_at = BigIntegerField()

    share_id = CharField(null=True, unique=True)
    archived = BooleanField(default=False)

    class Meta:
        database = DB


class ChatModel(BaseModel):
    id: str
    thread_id: Optional[str] = None
    user_id: str
    title: str
    chat: str

    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch

    share_id: Optional[str] = None
    archived: bool = False

class ThreadModel(BaseModel):
    id: str
    user_id: str
    created_at: int  # timestamp in epoch


####################
# Forms
####################


class ChatForm(BaseModel):
    chat: dict


class ChatTitleForm(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: str
    thread_id: Optional[str] = None
    user_id: str
    title: str
    chat: dict
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch
    share_id: Optional[str] = None  # id of the chat to be shared
    archived: bool


class ChatTitleIdResponse(BaseModel):
    id: str
    title: str
    updated_at: int
    created_at: int

class ThreadTable:
    def __init__(self, db):
        self.db = db
        db.create_tables([Thread])

    def create_thread(self, user_id: str) -> ThreadModel:
        id = str(uuid.uuid4())
        thread = ThreadModel(
            **{
                "id": id,
                "user_id": user_id,
                "created_at": int(time.time()),
            }
        )

        result = Thread.create(**thread.dict())
        return thread if result else None

    def get_thread_by_id(self, id: str) -> Optional[ThreadModel]:
        try:
            thread = Thread.get(Thread.id == id)
            return ThreadModel(**model_to_dict(thread))
        except:
            return None


class ChatTable:
    def __init__(self, db):
        self.db = db
        db.create_tables([Chat, Thread])

    def insert_new_chat(self, user_id: str, form_data: ChatForm, thread_id: Optional[str] = None) -> Optional[ChatModel]:
        id = str(uuid.uuid4())
        chat_data = {
            "id": id,
            "user_id": user_id,
            "title": form_data.chat.get("title", "New Chat"),
            "chat": json.dumps(form_data.chat),
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "thread_id": thread_id  # Add the thread_id to the chat data
        }
        chat = ChatModel(**chat_data)
        result = Chat.create(**chat.dict(exclude_unset=True))
        return chat if result else None

    def update_chat_by_id(self, id: str, chat: dict) -> Optional[ChatModel]:
        try:
            if "thread_id" in chat:
                query = Chat.update(
                chat=json.dumps(chat),
                title=chat["title"] if "title" in chat else "New Chat",
                thread_id=chat["thread_id"],
                updated_at=int(time.time()),
            ).where(Chat.id == id)
            else:
                query = Chat.update(
                    chat=json.dumps(chat),
                    title=chat["title"] if "title" in chat else "New Chat",
                    updated_at=int(time.time()),
                ).where(Chat.id == id)
            query.execute()

            chat = Chat.get(Chat.id == id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def insert_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        # Get the existing chat to share
        chat = Chat.get(Chat.id == chat_id)
        # Check if the chat is already shared
        if chat.share_id:
            return self.get_chat_by_id_and_user_id(chat.share_id, "shared")
        # Create a new chat with the same data, but with a new ID
        shared_chat = ChatModel(
            **{
                "id": str(uuid.uuid4()),
                "user_id": f"shared-{chat_id}",
                "thread_id": chat.thread_id,
                "title": chat.title,
                "chat": chat.chat,
                "created_at": chat.created_at,
                "updated_at": int(time.time()),
            }
        )#possible that **shared_chat.model_dump() is needed
        shared_result = Chat.create(**shared_chat.dict())
        # Update the original chat with the share_id
        result = (
            Chat.update(share_id=shared_chat.id).where(Chat.id == chat_id).execute()
        )

        return shared_chat if (shared_result and result) else None

    def update_shared_chat_by_chat_id(self, chat_id: str) -> Optional[ChatModel]:
        try:
            print("update_shared_chat_by_id")
            chat = Chat.get(Chat.id == chat_id)
            print(chat)

            query = Chat.update(
                title=chat.title,
                chat=chat.chat,
            ).where(Chat.id == chat.share_id)

            query.execute()

            chat = Chat.get(Chat.id == chat.share_id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def delete_shared_chat_by_chat_id(self, chat_id: str) -> bool:
        try:
            query = Chat.delete().where(Chat.user_id == f"shared-{chat_id}")
            query.execute()  # Remove the rows, return number of rows removed.

            return True
        except:
            return False

    def update_chat_share_id_by_id(
        self, id: str, share_id: Optional[str]
    ) -> Optional[ChatModel]:
        try:
            query = Chat.update(
                share_id=share_id,
            ).where(Chat.id == id)
            query.execute()

            chat = Chat.get(Chat.id == id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def toggle_chat_archive_by_id(self, id: str) -> Optional[ChatModel]:
        try:
            chat = self.get_chat_by_id(id)
            query = Chat.update(
                archived=(not chat.archived),
            ).where(Chat.id == id)

            query.execute()

            chat = Chat.get(Chat.id == id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def get_archived_chat_list_by_user_id(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> List[ChatModel]:
        return [
            ChatModel(**model_to_dict(chat))
            for chat in Chat.select()
            .where(Chat.archived == True)
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
            # .limit(limit)
            # .offset(skip)
        ]

    def get_chat_list_by_user_id(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> List[ChatModel]:
        return [
            ChatModel(**model_to_dict(chat))
            for chat in Chat.select()
            .where(Chat.archived == False)
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
            # .limit(limit)
            # .offset(skip)
        ]

    def get_chat_list_by_chat_ids(
        self, chat_ids: List[str], skip: int = 0, limit: int = 50
    ) -> List[ChatModel]:
        return [
            ChatModel(**model_to_dict(chat))
            for chat in Chat.select()
            .where(Chat.archived == False)
            .where(Chat.id.in_(chat_ids))
            .order_by(Chat.updated_at.desc())
        ]

    def get_chat_by_id(self, id: str) -> Optional[ChatModel]:
        try:
            chat = Chat.get(Chat.id == id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def get_chat_by_share_id(self, id: str) -> Optional[ChatModel]:
        try:
            chat = Chat.get(Chat.share_id == id)

            if chat:
                chat = Chat.get(Chat.id == id)
                return ChatModel(**model_to_dict(chat))
            else:
                return None
        except:
            return None

    def get_chat_by_id_and_user_id(self, id: str, user_id: str) -> Optional[ChatModel]:
        try:
            chat = Chat.get(Chat.id == id, Chat.user_id == user_id)
            return ChatModel(**model_to_dict(chat))
        except:
            return None

    def get_chats(self, skip: int = 0, limit: int = 50) -> List[ChatModel]:
        return [
            ChatModel(**model_to_dict(chat))
            for chat in Chat.select().order_by(Chat.updated_at.desc())
            # .limit(limit).offset(skip)
        ]

    def get_chats_by_user_id(self, user_id: str) -> List[ChatModel]:
        return [
            ChatModel(**model_to_dict(chat))
            for chat in Chat.select()
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
            # .limit(limit).offset(skip)
        ]

    def delete_chat_by_id(self, id: str) -> bool:
        try:
            query = Chat.delete().where((Chat.id == id))
            query.execute()  # Remove the rows, return number of rows removed.

            return True and self.delete_shared_chat_by_chat_id(id)
        except:
            return False

    def delete_chat_by_id_and_user_id(self, id: str, user_id: str) -> bool:
        try:
            query = Chat.delete().where((Chat.id == id) & (Chat.user_id == user_id))
            query.execute()  # Remove the rows, return number of rows removed.

            return True and self.delete_shared_chat_by_chat_id(id)
        except:
            return False

    def delete_chats_by_user_id(self, user_id: str) -> bool:
        try:

            self.delete_shared_chats_by_user_id(user_id)

            query = Chat.delete().where(Chat.user_id == user_id)
            query.execute()  # Remove the rows, return number of rows removed.

            return True
        except:
            return False

    def delete_shared_chats_by_user_id(self, user_id: str) -> bool:
        try:
            shared_chat_ids = [
                f"shared-{chat.id}"
                for chat in Chat.select().where(Chat.user_id == user_id)
            ]

            query = Chat.delete().where(Chat.user_id << shared_chat_ids)
            query.execute()  # Remove the rows, return number of rows removed.

            return True
        except:
            return False


Chats = ChatTable(DB)
