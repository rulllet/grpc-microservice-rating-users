import sys
import grpc
from concurrent import futures
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

import rating_pb2
import rating_pb2_grpc


SQLALCHEMY_DATABASE_URL = 'sqlite:///rating.db'

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autoflush=False, bind=engine)

Base = declarative_base()

class Rating(Base):
    __tablename__ = "rating"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, unique=True)
    nickname = Column(String)
    total_correct = Column(Integer)
    total_wrong = Column(Integer)

Base.metadata.create_all(bind=engine)

@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_rating() -> list:
    with session_scope() as db:
        rating = db.query(Rating).order_by((Rating.total_correct + Rating.total_wrong).desc()).limit(20).all()
        if rating:
            return [(i.user_id, i.nickname, i.total_correct, i.total_wrong) for i in rating]

def get_user_rating(user_id: int) -> tuple:
    with session_scope() as db:
        rating = db.query(Rating).filter(Rating.user_id == user_id).first()
        if rating:
            return (rating.user_id,
                    rating.nickname,
                    rating.total_correct,
                    rating.total_wrong)

def init_rating(user_id: int) -> bool:
    with session_scope() as db:
        if db.query(Rating).filter(Rating.user_id == user_id).first():
            return False
        w = Rating(user_id=user_id, nickname='Some user 🐟', total_correct=0, total_wrong=0)
        db.merge(w)
        return True

def update_correct_rating(user_id: int) -> bool:
    with session_scope() as db:
        w = db.query(Rating).filter(Rating.user_id == user_id).one_or_none()
        if w:
            w.total_correct += 1
            return True
        return False

def update_wrong_rating(user_id: int) -> bool:
    with session_scope() as db:
        w = db.query(Rating).filter(Rating.user_id == user_id).one_or_none()
        if w:
            w.total_wrong += 1
            return True
        return False

def change_nickname(user_id: int, nickname: str) -> bool:
    with session_scope() as db:
        w = db.query(Rating).filter(Rating.user_id == user_id).one_or_none()
        if w:
            w.nickname = nickname
            return True
        return False

def delete_user(user_id: int) -> bool:
    with session_scope() as db:
        w = db.query(Rating).filter(Rating.user_id == user_id).one_or_none()
        if w:
            db.delete(w)
            return True
        return False

class RatingServicer(rating_pb2_grpc.RatingServicer):
    def RatingUser(self, request, context):
        response = rating_pb2.RatingUserResponse()
        data = get_user_rating(request.id)
        if data:
            response.user_id, response.nickname, response.total_correct, response.total_wrong = data
            return response

    def RatingTop(self, request, context):
        response = rating_pb2.RatingTopResponse(
            top_users=[rating_pb2.RatingUserResponse(
                user_id=i[0], nickname=i[1], total_correct=i[2], total_wrong=i[3]) for i in get_rating()]
        )
        return response

    def InitRating(self, request, context):
        return self.update_rating(request, context, init_rating)

    def UpdateCorrect(self, request, context):
        return self.update_rating(request, context, update_correct_rating)

    def UpdateWrong(self, request, context):
        return self.update_rating(request, context, update_wrong_rating)

    def DeleteUser(self, request, context):
        return self.update_rating(request, context, delete_user)

    def ChangeNickname(self, request, context):
        return self.update_rating(request, context, lambda id: change_nickname(id, request.nick))

    @staticmethod
    def update_rating(request, context, update_func):
        response = rating_pb2.ChangeStatusRequest()
        if update_func(request.id):
            response.id = 1
            return response
        response.id = 0
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rating_pb2_grpc.add_RatingServicerServicer_to_server(RatingServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    try:
        serve()
    except KeyboardInterrupt:
        print('Exiting')
        sys.exit()