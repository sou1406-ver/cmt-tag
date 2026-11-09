"""Terminal input loop using the existing Store and run_posts collector."""
import json

from .browser import collect, run_posts
from .parser import facebook_url
from .store import write_json


def session(store,page,read_line=input,collector=collect,movie_id=None,emit=print,data_root='data'):
    if not store.config.get('interactive'):
        raise ValueError('Resume interactive requires an interactive run')
    state=store.path/'interactive_state.json'
    try:
        saved=json.loads(state.read_text(encoding='utf-8')).get('movie_id') if state.exists() else None
        if movie_id is None or not movie_id.strip():
            while not movie_id:
                movie_id=read_line(f'Mã phim{f" [{saved}]" if saved else ""}: ').strip() or saved
        write_json(state,{'movie_id':movie_id})
        while True:
            line=read_line('Dán link (Enter để kết thúc):').strip().strip('\'"').strip()
            if not line:
                store.finish()
                break
            if line.casefold()=='movie' or line.casefold().startswith('movie '):
                value=line[5:].strip()
                if not value: emit('Dùng movie <mã mới>.'); continue
                movie_id=value; write_json(state,{'movie_id':movie_id})
                emit('Mã phim: '+movie_id); continue
            try:
                url=facebook_url(line)
            except ValueError as exc:
                emit('Link không hợp lệ: '+str(exc)); continue
            latest={p['post_url']:p for p in store.posts}
            if url in latest and latest[url]['status']=='success':
                emit('Bài này đã cào thành công trong run, bỏ qua.'); continue
            existing=next((p for p in store.config['posts'] if p['post_url']==url),None)
            post=existing or {'post_url':url,'movie_id':movie_id}
            try:
                store.add_post(post)
            except ValueError as exc:
                emit(str(exc)); continue
            before=len(store.rows)
            run_posts(store,page,collector=collector,posts=[post],finalize=False)
            result=store.posts[-1]
            emit(f"status={result['status']} reason={result['reason']} | comment mới={len(store.rows)-before} | tổng run={len(store.rows)}")
    except (KeyboardInterrupt,EOFError):
        store.checkpoint('interrupted')
        emit('Đã dừng; journal được giữ, dùng --resume để tiếp tục.')
        return_code=130
    else:
        return_code=0
    emit('run_id: '+store.run_id)
    emit('Thư mục: '+str(store.path.resolve()))
    suffix='' if str(data_root)=='data' else ' --data-root '+json.dumps(str(data_root),ensure_ascii=False)
    emit('python -m src.crawler validate --run '+store.run_id+suffix)
    emit('python -m src.crawler export  --run '+store.run_id+suffix)
    return return_code
