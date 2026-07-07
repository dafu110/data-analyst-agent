# Data Analyst Agent 蹇€熶娇鐢ㄦ寚鍗?
杩欐槸涓€涓腑鏂囨暟鎹垎鏋?Agent锛岀敤浜?CSV / Excel 鏁版嵁闆嗙殑鑷姩鐢诲儚銆佷笟鍔″瓧娈佃瘑鍒€佸浘琛ㄥ缓璁€佺鐞嗘憳瑕併€佽川閲忛棬绂併€佹姤鍛婂鍑哄拰杩介棶銆?
## 鏈湴杩愯

```powershell
cd "C:\Users\lenovo\Desktop\AGENT\data-analyst-agent"
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
```

鎵撳紑搴旂敤锛?
```text
http://127.0.0.1:8002
```

OpenAPI 鏂囨。锛?
```text
http://127.0.0.1:8002/docs
```

濡傛灉 8002 琚崰鐢紝鍙互鎹㈡垚 8003 鎴栧叾浠栫鍙ｃ€?
## 瀹夎渚濊禆

```powershell
python -m pip install -e .[prod]
```

鍥藉唴缃戠粶杈冩參鏃讹細

```powershell
python -m pip install -e .[prod] -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 鎺ㄨ崘浣跨敤鏂瑰紡

1. 涓婁紶 CSV 鎴?Excel 鏂囦欢銆?2. 閫夋嫨涓氬姟鍦烘櫙锛屼緥濡傞攢鍞€佺數鍟嗐€佽储鍔°€佸鎴疯繍钀ャ€?3. 閫夋嫨鍒嗘瀽娣卞害锛?   - 蹇€熻瘖鏂細閫傚悎蹇€熺湅闂銆?   - 鏍囧噯鍒嗘瀽锛氶€傚悎鏃ュ父浣跨敤銆?   - 娣卞害澶嶇洏锛氫細杈撳嚭鏇村 trace銆佹寚鏍囧彛寰勫拰鍘熷缁撴灉銆?4. 閫夋嫨浜や粯鏍煎紡锛?   - 涓氬姟鎶ュ憡锛氶€傚悎鍒嗘瀽甯堝拰涓氬姟璐熻矗浜恒€?   - 绠＄悊鎽樿锛氶€傚悎鑰佹澘鎴栫鐞嗗眰銆?   - 璇婃柇娓呭崟锛氶€傚悎妫€鏌ユ暟鎹川閲忓拰瀛楁鍙ｅ緞銆?5. 鐐瑰嚮寮€濮嬪垎鏋愶紝瀹屾垚鍚庢煡鐪嬪浘琛ㄣ€佹姤鍛娿€佽拷闂拰瀵煎嚭銆?
## 褰撳墠鑳藉姏

- CSV / Excel 澶?sheet 鏁版嵁鍒嗘瀽
- 鏁版嵁璐ㄩ噺璇勫垎銆佺己澶卞€笺€侀噸澶嶈銆佸父閲忓瓧娈垫鏌?- 涓氬姟璇箟璇嗗埆锛氭敹鍏ャ€侀攢閲忋€佸尯鍩熴€佷骇鍝併€佹棩鏈熴€佹垚鏈€佸埄娑︾瓑
- 鑷姩鐢熸垚鍒嗘瀽璁″垝銆佸叧閿礊瀵熴€佽鍔ㄥ缓璁拰鎸囨爣鍙ｅ緞
- 鍥捐〃瑙勬牸锛氭煴鐘跺浘銆佽秼鍔垮浘銆佹暟鍊艰寖鍥村浘銆佸垎缁勮础鐚浘
- 瀵煎嚭 Markdown銆丠TML銆丆SV 鎽樿銆丳DF銆丳PTX
- 浠诲姟鍘嗗彶銆佺姸鎬佹椂闂寸嚎銆佸彇娑堜换鍔°€佸璁℃棩蹇椼€佽繍琛屾寚鏍?- FastAPI / OpenAPI銆丳ostgreSQL銆丷edis/RQ worker銆丏ocker 娌欑鍏ュ彛

## 鐢熶骇杩愯寤鸿

鐢熶骇鐜寤鸿浣跨敤锛?
```powershell
python -m backend.fastapi_app --host 0.0.0.0 --port 8000
python -m backend.worker
```

寤鸿閰嶇疆锛?
```text
DATA_ANALYST_AGENT_API_TOKEN
DATA_ANALYST_AGENT_DATABASE_URL
DATA_ANALYST_AGENT_REDIS_URL
DATA_ANALYST_AGENT_EXECUTOR_MODE=docker
DATA_ANALYST_AGENT_MAX_UPLOAD_MB
DATA_ANALYST_AGENT_MAX_CONCURRENT_JOBS
DATA_ANALYST_AGENT_RATE_LIMIT_PER_MINUTE
```

## 楠岃瘉鍛戒护

```powershell
python -m compileall data_analyst_agent backend evals
node --check frontend\app.js
python -m unittest discover -s tests
python -m evals.run_evals
```

## 甯歌闂

### 绔彛琚崰鐢?
鎹竴涓鍙ｏ細

```powershell
python -m backend.fastapi_app --host 127.0.0.1 --port 8003
```

### PDF 涓枃涔辩爜

褰撳墠鐗堟湰宸茶嚜鍔ㄥ祵鍏ヤ腑鏂囧瓧浣撱€備慨鏀逛唬鐮佸悗闇€瑕侀噸鍚湇鍔★紝骞堕噸鏂板鍑?PDF銆?
### Excel 璇诲彇澶辫触

瀹夎鐢熶骇渚濊禆锛?
```powershell
python -m pip install -e .[prod]
```

### 鎶ュ憡鍙湁灏戦噺鍥捐〃

閫夋嫨锛?
```text
鍒嗘瀽娣卞害锛氭繁搴﹀鐩?浜や粯鏍煎紡锛氫笟鍔℃姤鍛?```
