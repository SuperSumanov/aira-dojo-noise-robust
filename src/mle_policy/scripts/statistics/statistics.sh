python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1022/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-score-day5-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1021/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-score-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1020/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1014/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-metric-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1013/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/online-grpo-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/0918/chaii-hindi-and-tamil-question-answering/7200/qwen-medium/mcts \
  --interval 1800 \
  --output tmp/examples/online/chaii-hindi-and-tamil-question-answering-comparison.png \
  --title "CHAIi Hindi and Tamil Question Answering" \
  --text > tmp/chaii.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1023/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-metric-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1022/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-score-day5-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1021/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-score-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1020/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1014/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-metric-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1013/tgs-salt-identification-challenge/7200/qwen-medium/online-grpo-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1012/tgs-salt-identification-challenge/7200/qwen-off/mcts \
  --interval 1800 \
  --output tmp/examples/online/tgs-salt-identification-challenge-comparison.png \
  --title "TGS Salt Identification Challenge" \
  --text > tmp/tgs.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1023/dog-breed-identification/7200/qwen-medium/online-grpo-metric-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1022/dog-breed-identification/7200/qwen-medium/online-grpo-score-day5-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1021/dog-breed-identification/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/dog-breed-identification/7200/qwen-medium/online-grpo-day4-score-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1020/dog-breed-identification/7200/qwen-medium/online-grpo-day4-score-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/dog-breed-identification/7200/qwen-medium/online-grpo-day3-metric-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/dog-breed-identification/7200/qwen-medium/online-grpo-day3-score-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/dog-breed-identification/7200/qwen-medium/online-grpo-day2-metric-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/dog-breed-identification/7200/qwen-medium/online-grpo-day2-score-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1014/dog-breed-identification/7200/qwen-medium/online-grpo-metric-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1013/dog-breed-identification/7200/qwen-medium/online-grpo-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1009/dog-breed-identification/7200/qwen-medium/random \
  --interval 1800 \
  --output tmp/examples/online/dog-breed-identification-comparison.png \
  --title "Dog Breed Identification" \
  --text > tmp/dog-breed.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1023/bms-molecular-translation/7200/qwen-medium/online-grpo-metric-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1022/bms-molecular-translation/7200/qwen-medium/online-grpo-score-day5-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1021/bms-molecular-translation/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/bms-molecular-translation/7200/qwen-medium/online-grpo-score-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1020/bms-molecular-translation/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/bms-molecular-translation/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/bms-molecular-translation/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/bms-molecular-translation/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/bms-molecular-translation/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1014/bms-molecular-translation/7200/qwen-medium/online-grpo-metric-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1013/bms-molecular-translation/7200/qwen-medium/online-grpo-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1001/bms-molecular-translation/7200/qwen-medium/mcts \
  --interval 1800 \
  --output tmp/examples/online/bms-molecular-translation-comparison.png \
  --title "BMS Molecular Translation" \
  --text > tmp/bms.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1023/champs-scalar-coupling/7200/qwen-medium/online-grpo-metric-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1022/champs-scalar-coupling/7200/qwen-medium/online-grpo-score-day5-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1021/champs-scalar-coupling/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/champs-scalar-coupling/7200/qwen-medium/online-grpo-score-day4-step66-lora-1 \
  data/augmented_mle_critic/raw_journal/comparison/1020/champs-scalar-coupling/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/champs-scalar-coupling/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/champs-scalar-coupling/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/champs-scalar-coupling/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/champs-scalar-coupling/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1014/champs-scalar-coupling/7200/qwen-medium/online-grpo-metric-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1013/champs-scalar-coupling/7200/qwen-medium/online-grpo-v1-step30-lora \
  data/augmented_mle_critic/raw_journal/comparison/1001/champs-scalar-coupling/qwen-medium/mcts \
  --interval 1800 \
  --output tmp/examples/online/champs-scalar-coupling-comparison.png \
  --title "Champs Scalar Coupling" \
  --text > tmp/champs.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1021/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/aptos2019-blindness-detection/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  --interval 1800 \
  --output tmp/examples/online/aptos2019-blindness-detection-comparison.png \
  --title "Aptos2019 Blindness Detection" \
  --text > tmp/aptos.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1021/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/facebook-recruiting-iii-keyword-extraction/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  --interval 1800 \
  --output tmp/examples/online/facebook-recruiting-iii-keyword-extraction-comparison.png \
  --title "Facebook Recruiting III Keyword Extraction" \
  --text > tmp/facebook.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1021/kuzushiji-recognition/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/kuzushiji-recognition/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/kuzushiji-recognition/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/kuzushiji-recognition/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/kuzushiji-recognition/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/kuzushiji-recognition/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  --interval 1800 \
  --output tmp/examples/online/kuzushiji-recognition-comparison.png \
  --title "Kuzushiji Recognition" \
  --text > tmp/kuzushiji.txt

python src/dojo/analysis_utils/journal_to_fig.py \
  data/augmented_mle_critic/raw_journal/comparison/1021/tensorflow2-question-answering/7200/qwen-medium/online-grpo-metric-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1020/tensorflow2-question-answering/7200/qwen-medium/online-grpo-score-day4-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1018/tensorflow2-question-answering/7200/qwen-medium/online-grpo-metric-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1017/tensorflow2-question-answering/7200/qwen-medium/online-grpo-score-day3-step66-lora \
  data/augmented_mle_critic/raw_journal/comparison/1016/tensorflow2-question-answering/7200/qwen-medium/online-grpo-metric-day2-step70-lora \
  data/augmented_mle_critic/raw_journal/comparison/1015/tensorflow2-question-answering/7200/qwen-medium/online-grpo-score-day2-step70-lora \
  --interval 1800 \
  --output tmp/examples/online/tensorflow2-question-answering-comparison.png \
  --title "TensorFlow2 Question Answering" \
  --text > tmp/tensorflow2.txt