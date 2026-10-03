from fastapi import APIRouter, HTTPException

from core.account_pool import get_pool

router = APIRouter()


@router.get("")
async def accounts_status():
    pool = get_pool()
    try:
        if not pool.accounts:
            pool.load()
    except FileNotFoundError as e:
        return {"accounts": [], "ip_blocked_until": None, "error": str(e)}
    return pool.status()


@router.post("/reload")
async def reload_accounts():
    """Đọc lại accounts.json (sau khi thêm tài khoản / cập nhật cookie)."""
    try:
        get_pool().load()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"accounts.json lỗi: {e}")
    return get_pool().status()


@router.post("/check")
async def check_accounts():
    """Đọc lại accounts.json rồi đăng nhập thử từng tài khoản (không tốn hạn mức)."""
    try:
        return await get_pool().check_all()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"accounts.json lỗi: {e}")
