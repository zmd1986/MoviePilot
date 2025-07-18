from typing import Optional

from sqlalchemy import Column, Integer, String, Sequence, JSON
from sqlalchemy.orm import Session

from app.db import db_query, Base


class Message(Base):
    """
    消息表
    """
    id = Column(Integer, Sequence('id'), primary_key=True, index=True)
    # 消息渠道
    channel = Column(String)
    # 消息来源
    source = Column(String)
    # 消息类型
    mtype = Column(String)
    # 标题
    title = Column(String)
    # 文本内容
    text = Column(String)
    # 图片
    image = Column(String)
    # 链接
    link = Column(String)
    # 用户ID
    userid = Column(String)
    # 登记时间
    reg_time = Column(String, index=True)
    # 消息方向：0-接收息，1-发送消息
    action = Column(Integer)
    # 附件json
    note = Column(JSON)

    @staticmethod
    @db_query
    def list_by_page(db: Session, page: Optional[int] = 1, count: Optional[int] = 30):
        return db.query(Message).order_by(Message.reg_time.desc()).offset((page - 1) * count).limit(count).all()
