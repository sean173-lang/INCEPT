"""Loopback helper for isolated fixture workflows; blocks outbound socket connections."""

def main():
    import socket
    import uvicorn
    from scripts.http_service import create_app
    def deny(*args,**kwargs):
        raise RuntimeError('Isolated fixture service prohibits outbound connections')
    socket.socket.connect=deny
    socket.socket.connect_ex=deny
    app=create_app(development=True,allow_paid=False,cache_dir=None,ledger_path=None,
        onboarding_db='data/incept_corporate_execution_test.sqlite3',corporate_cache_dir='data/incept_test_empty_cache')
    uvicorn.run(app,host='127.0.0.1',port=8004,access_log=False)

if __name__=='__main__':main()
