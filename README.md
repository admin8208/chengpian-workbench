# 鎴愮墖宸ヤ綔鍙?
`鎴愮墖宸ヤ綔鍙癭 鏄竴涓潰鍚戝崟鏈?/ 绉佹湁鍖栭儴缃插満鏅殑瑙嗛鐢熶骇宸ヤ綔鍙般€?
褰撳墠浜у搧涓荤嚎鑱氱劍浜庢枃妗堝垱浣滐細浠庨」鐩爣棰樸€佸師鏂囥€佽剼鏈?鍒嗛暅銆侀厤闊冲瓧骞曘€佺礌鏉愯ˉ榻愬埌鏈€缁堟垚鐗囪緭鍑恒€?
褰撳墠榛樿杩愯褰㈡€侊細

- 鍓嶇鏋勫缓浜х墿锛歚apps/web/dist`
- API 鏈嶅姟锛歚apps/api/run_api.py`
- Worker 鏈嶅姟锛歚apps/api/run_worker.py`
- 涓氬姟鏁版嵁搴擄細PostgreSQL
- 浠诲姟闃熷垪锛歊edis锛圚uey 鍚庣锛?- 鏈湴杩愯鐩綍锛歚data/`

Windows 杩愯璇存槑锛?
- 寮€鍙?璋冭瘯/鐢熶骇鑴氭湰鐜板湪浼氶€氳繃 `scripts/windows/run_worker_supervisor.ps1` 鎷夎捣 worker銆?- 璇?supervisor 浼氬湪 `run_worker.py` 鎰忓閫€鍑哄悗鑷姩閲嶅惎锛岄伩鍏嶄换鍔￠暱鏈熷仠鍦?`queued` 鎴栨畫鐣欏亣 `running` 鐘舵€併€?
## 鏍稿績鑳藉姏

- 鍒涘缓鏂囨鍒涗綔椤圭洰骞堕€夋嫨璧涢亾 / 绱犳潗妯″紡
- 鐢熸垚瑙嗛銆佺户缁敓鎴愩€侀噸璺戝叏閮?- 鍒嗛暅绱犳潗绾犲亸涓庨暅澶寸骇浜哄伐淇
- 鍦ㄧ嚎 / 绂荤嚎閰嶉煶涓庡瓧骞曢瑙?- 鏈€缁堟垚鐗囨覆鏌撲笌鍘嗗彶杈撳嚭绠＄悊
- 绱犳潗搴撶鐞嗕笌缃戠洏瀵煎叆
- 澶фā鍨嬨€佺敓鍥俱€佺礌鏉愭簮銆乀TS 閰嶇疆涓庡仴搴锋鏌?- 绠＄悊鍛樺垵濮嬪寲銆佺櫥褰曘€佸瓙璐﹀彿绠＄悊

## 鐩綍缁撴瀯

```text
/opt/chengpian-workbench/
  apps/
    api/
    web/
  data/
  deploy/
  docs/
  scripts/
```

璇存槑锛?
- `apps/api/`锛欶astAPI 鍚庣銆佷换鍔″鐞嗐€佹暟鎹簱妯″瀷涓庝笟鍔￠€昏緫
- `apps/web/`锛歏ue 3 鍓嶇
- `data/`锛氭湰鏈鸿繍琛屾暟鎹紝鍖呭惈绱犳潗銆佸鍑烘枃浠躲€佺紦瀛樸€佹棩蹇楀拰鏈満鐢熸垚鐨勫瘑閽ワ紱涓嶅睘浜庢簮鐮?- `deploy/`锛歯ginx 涓?systemd 妯℃澘
- `docs/`锛氶儴缃蹭笌鏁寸悊涓殑椤圭洰鏂囨。
- `scripts/`锛氬紑鍙?鐢熶骇杈呭姪鑴氭湰

## 鏁版嵁杈圭晫

- PostgreSQL锛氬瓨鏀鹃」鐩€侀暅澶淬€佷换鍔°€侀厤缃€佽处鍙枫€丳rovider 鍏冩暟鎹瓑缁撴瀯鍖栦笟鍔℃暟鎹?- Redis锛氬瓨鏀?Huey 浠诲姟闃熷垪娑堟伅
- `data/`锛氬瓨鏀剧礌鏉愭枃浠躲€佸鍑鸿棰戝拰鍏朵粬鏈満鏂囦欢浜х墿

婧愮爜涓庤繍琛屾暟鎹竟鐣岋細

- `apps/`銆乣deploy/`銆乣docs/`銆乣scripts/` 鏄簮鐮併€侀儴缃叉ā鏉垮拰鏂囨。
- `data/`銆乣.env.local`銆佹棩蹇椼€佺紦瀛樸€佹瀯寤轰骇鐗┿€佽櫄鎷熺幆澧冨拰渚濊禆鐩綍鏄湰鏈鸿繍琛?寮€鍙戜骇鐗╋紝涓嶅簲绾冲叆鐗堟湰绠＄悊
- 鐢熶骇鐜寤鸿鏄惧紡璁剧疆 `CHENGPIAN_DATA_DIR` 鍒版簮鐮佺洰褰曚箣澶栵紝渚嬪 `/var/lib/chengpian`
- 瀵嗛挜鏂囦欢鍜岀湡瀹炵幆澧冨彉閲忓彧搴斿湪鐩爣鏈哄櫒鐢熸垚鎴栭厤缃紝涓嶅簲闅忎唬鐮佸垎鍙?
褰撳墠鍚庣鍙敮鎸?PostgreSQL 浣滀负涓氬姟鏁版嵁搴撱€?
蹇呴渶鐜鍙橀噺锛?
```bash
export CHENGPIAN_DATABASE_URL=postgresql+psycopg://chengpian:password@127.0.0.1:5432/chengpian
```

## 鍏抽敭鏂囨。

- 鎬讳綋閮ㄧ讲璇存槑锛歚docs/deployment/deployment.md`
- Linux 閮ㄧ讲姝ラ锛歚docs/deployment/deployment-linux.md`
- 绯荤粺鏋舵瀯璇存槑锛歚docs/architecture/architecture.md`
- 閰嶇疆椤规竻鍗曪細`docs/operations/configuration.md`
- 鍓嶇褰撳墠璺敱涓庨〉闈㈣竟鐣岋細`apps/web/README.md`
- 璧勪骇杈圭晫涓庡瓨鍌ㄧ害瀹氾細`docs/architecture/project-asset-boundary.md`
- 璧勪骇杈圭晫瀹¤璇存槑锛歚docs/operations/asset-audit-runbook.md`
- 鍘嗗彶閲嶆瀯璁″垝锛歚docs/plans/refactor-plan.md`

## 蹇€熷畾浣?
- 鍓嶇鍏ュ彛锛歚apps/web/src/router.ts`
- API 鍏ュ彛锛歚apps/api/app/main.py`
- 鏁版嵁搴撹缃細`apps/api/app/settings.py`
- 鏁版嵁搴撳垵濮嬪寲锛歚apps/api/app/db.py`
- systemd 妯℃澘锛歚deploy/systemd/`

## 褰撳墠鐘舵€佽鏄?
- 褰撳墠榛樿閮ㄧ讲褰㈡€佷粛鐒舵槸鍗曟満
- 褰撳墠涓氬姟鏁版嵁搴撳凡缁忓垏鎹㈠埌 PostgreSQL
- `data/` 涓嶅啀鎵挎媴涓氬姟鏁版嵁搴撹亴璐?- 鍓嶇 README 宸叉寜褰撳墠鐪熷疄璺敱鏇存柊
- 鐢熶骇鐜涓嬩笉瑕佷互 `root` 鎵嬪伐鍚姩 API / Worker锛屽惁鍒?`data/` 鍙兘鍑虹幇 `root:root` 鏂囦欢骞跺鑷撮」鐩垹闄ゅけ璐?
## 鏈绾﹀畾

- `鏂囨鍒涗綔`锛氭寚浠庢爣棰?/ 鍘熸枃鍑哄彂锛岀粡鑴氭湰銆佸垎闀溿€侀厤闊炽€佺礌鏉愩€佹覆鏌撳緱鍒版垚鐗囩殑娴佺▼锛屽搴?`/creator/ai` 鎴?`/creator/network`

