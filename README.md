Заметки

OpenAO-API-Key:
***REMOVED***

Запуск кода:
1 python 01_prepare_audio.py data/example1.mp3
2 python 02_transcribe.py data/example1_16k_mono.wav --language ru --model large-v3 ОПЦИОНАЛЬНО: --threads 6
3 python 03_label_roles.py data/example1_16k_mono.transcript.txt
4 python 04_coach_replies.py data/example1.dialog.txt \
  --company "ВестКолл" \
  --goal "назначить демо на 15 минут" \
  --tone "спокойный, экспертный, без давления" \
  --company-info "Облачная телефония, омниканальные контакт-центры, интеграции с CRM (Bitrix24/amo/Salesforce), SLA 99.95%" \
  --constraints "не обещать скидку без подтверждения; не обещать интеграцию за 1 день" \
  --n-now 3 --n-soon 3 --n-later 3 --n-branch 3 --n-branch-opts 2 \
  --max-chars 180 --tail-turns 20 --tail-chars 2500 \
  --also-txt

full pipeline: python run_pipeline_slices.py \
  --input data/example_for_split.mp3 \
  --language ru \
  --asr-model large-v3 \
  --threads 6 \
  --coach-model gpt-4o-mini \
  --company "ВестКолл" \
  --goal "привлечь клиента и продать ему наши услуги" \
  --tone "спокойный, экспертный, проактивный, без давления" \
  --company-info "Облачная телефония и контакт-центры; интеграции с CRM (Bitrix24/amo/Salesforce); SLA 99.95%; быстрый пилот" \
  --constraints "не обещать скидки/сроки без согласования; не давать гарантий вне SLA" \
  --outdir outputs/example_for_split_fullrun

ТЗ:
ЛЛМ (РАГ) + Спич.рек. система помогающая оператору по продажам вести диалог с клиентом,
(Компания по продаже интернета)
Внутри БД есть данные о Клиенте и о предыдущих звонках
(3 Таблицы (История звонков, Таблица данных клиентов, Информация о компании))
Все должно происходить онлайн, средняя генерация текста должна быть около 1.5с