from fastapi import APIRouter, HTTPException
from typing import List
from services import session_service
from models import SessionResponse, SessionCreate, MessageInput

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=List[SessionResponse])
def list_sessions():
    return session_service.list_sessions()


@router.post("", response_model=SessionResponse)
def create_session(session_create: SessionCreate):
    try:
        return session_service.create_session(session_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: int):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
def kill_session(session_id: int):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_service.kill_session(session_id)
    return {"message": "Session killed"}


@router.delete("/{session_id}/data")
def delete_session_data(session_id: int):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_service.delete_session_data(session_id)
    return {"message": "Session data deleted"}


@router.delete("")
def clear_all_sessions():
    session_service.clear_all_sessions()
    return {"message": "All sessions cleared"}


@router.get("/{session_id}/events")
def get_session_events(session_id: int, after_id: int = 0):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    events = session_service.get_session_events(session_id, after_id)
    return {"events": events, "status": session["status"]}


@router.delete("/{session_id}/events")
def clear_session_events(session_id: int):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_service.clear_session_events(session_id)
    return {"message": "Session events cleared"}


@router.get("/{session_id}/history")
def get_session_history(session_id: int):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_service.get_session_history(session_id)


@router.post("/{session_id}/messages")
def send_session_message(session_id: int, message: MessageInput):
    session = session_service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        session_service.send_session_message(session_id, message.role, message.content)
        return {"message": "Message sent"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
