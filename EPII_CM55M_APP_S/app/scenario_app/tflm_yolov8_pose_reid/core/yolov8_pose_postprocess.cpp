#include "yolov8_pose_postprocess.h"
#include "xprintf.h"

// Actually box_iou is usually defined here or in yolo_postprocessing.h?
// yolo_postprocessing.h has do_nms_sort but not box_iou exposed?
// Let's implement box_iou here to be safe and self-contained.

float sigmoid(float x) {
    return 1.0f / (1.0f + expf(-x));
}

// Implementation of box_iou
float box_iou(box a, box b) {
    float area_a = a.w * a.h;
    float area_b = b.w * b.h;

    float w = std::min(a.x + a.w, b.x + b.w) - std::max(a.x, b.x);
    float h = std::min(a.y + a.h, b.y + b.h) - std::max(a.y, b.y);

    if (w <= 0 || h <= 0)
        return 0;

    float area_i = w * h;
    return area_i / (area_a + area_b - area_i);
}

bool yolov8_det_comparator(detection_cls_yolov8 &pa, detection_cls_yolov8 &pb)
{
    return pa.confidence > pb.confidence;
}

static void yolov8_NMSBoxes(std::vector<box> &boxes,std::vector<float> &confidences,float modelScoreThreshold,float modelNMSThreshold,std::vector<int>& nms_result)
{
    detection_cls_yolov8 yolov8_bbox;
    std::vector<detection_cls_yolov8> yolov8_bboxes{};
    for(int i = 0; i < boxes.size(); i++)
    {
        yolov8_bbox.bbox = boxes[i];
        yolov8_bbox.confidence = confidences[i];
        yolov8_bbox.index = i;
        yolov8_bboxes.push_back(yolov8_bbox);
    }
    sort(yolov8_bboxes.begin(), yolov8_bboxes.end(), yolov8_det_comparator);
    int updated_size = yolov8_bboxes.size();
    for(int k = 0; k < updated_size; k++)
    {
        if(yolov8_bboxes[k].confidence < modelScoreThreshold)
        {
            continue;
        }
        
        nms_result.push_back(yolov8_bboxes[k].index);
        for(int j = k + 1; j < updated_size; j++)
        {
            float iou = box_iou(yolov8_bboxes[k].bbox, yolov8_bboxes[j].bbox);
            if(iou > modelNMSThreshold)
            {
                yolov8_bboxes.erase(yolov8_bboxes.begin() + j);
                updated_size = yolov8_bboxes.size();
                j = j -1;
            }
        }

    }
}

static void softmax(float *input, size_t input_len) {
  // assert(input);

  float m = -INFINITY;
  for (size_t i = 0; i < input_len; i++) {
    if (input[i] > m) {
      m = input[i];
    }
  }

  float sum = 0.0;
  for (size_t i = 0; i < input_len; i++) {
    sum += expf(input[i] - m);
  }

  float offset = m + logf(sum);
  for (size_t i = 0; i < input_len; i++) {
    input[i] = expf(input[i] - offset);
  }
}

float yolov8_pose_bbox_dequant_value(int dims_cnt_1, int dims_cnt_2,TfLiteTensor* output)
{
	int value =  output->data.int8[ dims_cnt_2 + dims_cnt_1 * output->dims->data[2]];
			
	float deq_value = ((float) value-(float)((TfLiteAffineQuantization*)(output->quantization.params))->zero_point->data[0]) * ((TfLiteAffineQuantization*)(output->quantization.params))->scale->data[0];
	
    // FIX: YOLOv8 DFL outputs are raw logits/distributions. 
    // Do NOT apply coordinate scaling or sigmoid here.
    // The original code here was for YOLOv5/v7 style coordinates.
	return deq_value;
}

float yolov8_pose_key_pts_dequant_value(int dims_cnt_1, int dims_cnt_2,TfLiteTensor* output, float anchor_val_0, float anchor_val_1 , float stride_val)
{
	int value =  output->data.int8[ dims_cnt_2 + dims_cnt_1 * output->dims->data[2]];
			
	float deq_value = ((float) value-(float)((TfLiteAffineQuantization*)(output->quantization.params))->zero_point->data[0]) * ((TfLiteAffineQuantization*)(output->quantization.params))->scale->data[0];
	
	if(dims_cnt_2 % 3==0)
	{
		deq_value = ( deq_value * 2.0 +  (anchor_val_0 - 0.5) )* stride_val;
	}
	else if(dims_cnt_2 % 3==1)
	{
		deq_value = ( deq_value * 2.0 +  (anchor_val_1 - 0.5) )* stride_val;
	}
	else
	{
		deq_value = sigmoid(deq_value);
	}
	return deq_value;
}

void yolov8_pose_cal_xywh(int j,TfLiteTensor* output[7], box *bbox, float* anchor_756_2,float *stride_756_1, int *out_dim_size, int* box_indices )
{
    float  xywh_result[4];
    //do DFL (softmax and than do conv2d)
    int output_data_idx;
    for(int k = 0 ; k < 4 ; k++)
    {
        float tmp_arr_softmax_conv2d[16];
        float tmp_arr_softmax_conv2d_result=0;
        for(int i = 0 ; i < 16 ; i++)
        {
			float tmp_result = 0;
            if(j < out_dim_size[0])//576
            {
                output_data_idx = box_indices[0];
                tmp_result = yolov8_pose_bbox_dequant_value(j, k*16+i,output[output_data_idx]);
            }
            else if(j < out_dim_size[1])//720
            {
                output_data_idx = box_indices[1];
                tmp_result = yolov8_pose_bbox_dequant_value(j - out_dim_size[0], k*16+i,output[output_data_idx]);
            }
            else 
            {
                output_data_idx = box_indices[2];
                tmp_result = yolov8_pose_bbox_dequant_value(j - out_dim_size[1], k*16+i,output[output_data_idx]);
            }
            tmp_arr_softmax_conv2d[i] = tmp_result;
        }
        softmax(tmp_arr_softmax_conv2d,16);
        for(int i = 0 ; i < 16 ; i++)
        {

            tmp_arr_softmax_conv2d_result = tmp_arr_softmax_conv2d_result + tmp_arr_softmax_conv2d[i]*i;
        }
        xywh_result[k] = tmp_arr_softmax_conv2d_result;

    }

    /**dist2bbox * stride start***/
    float x1 = anchor_756_2[j * 2 + 0] -  xywh_result[0];
    float y1 = anchor_756_2[j * 2 + 1] -  xywh_result[1];
    float x2 = anchor_756_2[j * 2 + 0] +  xywh_result[2];
    float y2 = anchor_756_2[j * 2 + 1] +  xywh_result[3];
    
    float cx = (x1 + x2)/2.;
    float cy = (y1 + y2)/2.;
    float w = x2 - x1;
    float h = y2 - y1;

    xywh_result[0] = cx * stride_756_1[j];
    xywh_result[1] = cy * stride_756_1[j];
    xywh_result[2] = w * stride_756_1[j];
    xywh_result[3] = h * stride_756_1[j];

    // Debug raw DFL outputs
    // if (xywh_result[2] > 256 || xywh_result[3] > 256) {
    //    xprintf("Large Box Raw: j=%d, stride=%f, w_grid=%f, h_grid=%f, w_px=%f, h_px=%f\n", j, stride_756_1[j], w, h, xywh_result[2], xywh_result[3]);
    // }
    
    // Debug DFL values for specific indices (matching the candidates we saw)
    if (j >= 1299 && j <= 1316) {
        xprintf("DFL Debug j=%d: l=%d, t=%d, r=%d, b=%d (Grid W=%d, H=%d)\n", 
            j, (int)(xywh_result[0]*1000), (int)(xywh_result[1]*1000), (int)(xywh_result[2]*1000), (int)(xywh_result[3]*1000), (int)(w*1000), (int)(h*1000));
    }

    bbox->x = xywh_result[0] - (0.5 * xywh_result[2]);
    bbox->y = xywh_result[1] - (0.5 * xywh_result[3]);
    bbox->w = xywh_result[2];
    bbox->h = xywh_result[3];
    return ;
}

void yolov8_pose_post_processing(
    tflite::MicroInterpreter* static_interpreter,
    float modelScoreThreshold, 
    float modelNMSThreshold, 
    struct_yolov8_pose_algoResult *alg,
    std::forward_list<el_keypoint_t> &el_keypoint_algo,
    int dim_total_size,
    float* anchor_756_2,
    float* stride_756_1,
    uint32_t img_w,
    uint32_t img_h,
    uint32_t tensor_w,
    uint32_t tensor_h
)
{
    // uint32_t img_w = app_get_raw_width();
    // uint32_t img_h = app_get_raw_height();
    // Passed as arguments now

	TfLiteTensor* output[7];
	for(int i = 0; i < 7;i++)
	{
		output[i] = static_interpreter->output(i);
	}
	int output_data_idx = 0;

// Auto-detect indices based on shapes (assuming 192x192 input -> 576, 144, 36)
// If input size changes, these magic numbers need to be updated or calculated dynamically
int idx_stride_8 = -1;  // 24x24 = 576
int idx_stride_16 = -1; // 12x12 = 144
int idx_stride_32 = -1; // 6x6 = 36

// Box indices (64 channels)
int idx_box_8 = -1;
int idx_box_16 = -1;
int idx_box_32 = -1;

// Keypoint indices (51 channels)
int idx_kpt_8 = -1;
int idx_kpt_16 = -1;
int idx_kpt_32 = -1;

int numOutputs = static_interpreter->outputs_size();
for (int i = 0; i < numOutputs; i++) {
    TfLiteTensor* t = static_interpreter->output(i);
    if (t->dims->size >= 2) {
        int dim1 = t->dims->data[1];
        int channels = (t->dims->size > 2) ? t->dims->data[2] : 1;
        
        if (dim1 == 576) { // 192x192
            if (channels == 1) idx_stride_8 = i;
            else if (channels >= 64) idx_box_8 = i; 
            else if (channels == 51) idx_kpt_8 = i;
        }
        else if (dim1 == 144) {
            if (channels == 1) idx_stride_16 = i;
            else if (channels >= 64) idx_box_16 = i;
            else if (channels == 51) idx_kpt_16 = i;
        }
        else if (dim1 == 36) {
            if (channels == 1) idx_stride_32 = i;
            else if (channels >= 64) idx_box_32 = i;
            else if (channels == 51) idx_kpt_32 = i;
        }
        else if (dim1 == 1024) { // 256x256
            if (channels == 1) idx_stride_8 = i;
            else if (channels >= 64) idx_box_8 = i;
            else if (channels == 51) idx_kpt_8 = i;
        }
        else if (dim1 == 256) {
            if (channels == 1) idx_stride_16 = i;
            else if (channels >= 64) idx_box_16 = i;
            else if (channels == 51) idx_kpt_16 = i;
        }
        else if (dim1 == 64) {
            if (channels == 1) idx_stride_32 = i;
            else if (channels >= 64) idx_box_32 = i;
            else if (channels == 51) idx_kpt_32 = i;
        }
        else if (dim1 == 1344 || dim1 == 756) { // Concatenated keypoints (1024+256+64 or 576+144+36)
            if (channels == 51) {
                idx_kpt_8 = i;
                idx_kpt_16 = i;
                idx_kpt_32 = i;
            }
        }
    }
}

if (idx_stride_8 == -1 || idx_stride_16 == -1 || idx_stride_32 == -1) {
    xprintf("[ERROR] Could not find YOLO Score tensors! Indices: S8=%d, S16=%d, S32=%d\n", idx_stride_8, idx_stride_16, idx_stride_32);
    // Fallback to original hardcoded values if detection fails (though likely won't work)
    if(idx_stride_8 == -1) idx_stride_8 = 4;
    if(idx_stride_16 == -1) idx_stride_16 = 6;
    if(idx_stride_32 == -1) idx_stride_32 = 2;
} else {
    xprintf("[INFO] Auto-detected YOLO Score indices: S8=%d, S16=%d, S32=%d\n", idx_stride_8, idx_stride_16, idx_stride_32);
}
    
if (idx_box_8 == -1 || idx_box_16 == -1 || idx_box_32 == -1) {
    xprintf("[ERROR] Could not find YOLO Box tensors! Indices: B8=%d, B16=%d, B32=%d\n", idx_box_8, idx_box_16, idx_box_32);
    // Fallback
    if(idx_box_8 == -1) idx_box_8 = 1;
    if(idx_box_16 == -1) idx_box_16 = 0; 
    if(idx_box_32 == -1) idx_box_32 = 5;
} else {
    xprintf("[INFO] Auto-detected YOLO Box indices: B8=%d, B16=%d, B32=%d\n", idx_box_8, idx_box_16, idx_box_32);
}

if (idx_kpt_8 == -1 || idx_kpt_16 == -1 || idx_kpt_32 == -1) {
    xprintf("[ERROR] Could not find YOLO Keypoint tensors! Indices: K8=%d, K16=%d, K32=%d\n", idx_kpt_8, idx_kpt_16, idx_kpt_32);
    // Fallback - assuming 3 was the only one used before, but now we need 3
    if(idx_kpt_8 == -1) idx_kpt_8 = 3;
    if(idx_kpt_16 == -1) idx_kpt_16 = 3; 
    if(idx_kpt_32 == -1) idx_kpt_32 = 3; 
} else {
    xprintf("[INFO] Auto-detected YOLO Keypoint indices: K8=%d, K16=%d, K32=%d\n", idx_kpt_8, idx_kpt_16, idx_kpt_32);
}

int out_dim_total = 0;
// int numOutputs = static_interpreter->outputs_size(); // Already declared
int out_dim_size_num = 3; // We expect 3 scales
int out_dim_size[out_dim_size_num];
for(int out_num = 0; out_num < out_dim_size_num; out_num++)
{
    if(out_num==0)
    {
        output_data_idx = idx_stride_8;
    }
    else if(out_num==1)
    {
        output_data_idx = idx_stride_16;
    }
    else
    {
        output_data_idx = idx_stride_32;
    }
    out_dim_total += output[output_data_idx]->dims->data[1];
    out_dim_size[out_num] = out_dim_total;
}
// ///////////////////////
// // start postprocessing


std::vector<int> class_ids;
std::vector<float> confidences;
std::vector<box> boxes;
std::vector< struct_human_pose_17> kpts_vector;

// Optimization: Pre-calculate int8 thresholds to avoid dequantization and sigmoid for every anchor
float score_thresh_val = -logf(1.0f/modelScoreThreshold - 1.0f);
int8_t score_thresh_int8[3];
int indices[] = {idx_stride_8, idx_stride_16, idx_stride_32}; // The output indices used below
int box_indices[] = {idx_box_8, idx_box_16, idx_box_32};
int kpt_indices[] = {idx_kpt_8, idx_kpt_16, idx_kpt_32};

xprintf("Score Thresh Val: %d/1000 (Thresh=%d/1000)\n", (int)(score_thresh_val*1000), (int)(modelScoreThreshold*1000));
for(int i=0; i<3; i++) {
    TfLiteAffineQuantization* quant = (TfLiteAffineQuantization*)(output[indices[i]]->quantization.params);
    float scale = quant->scale->data[0];
    float zero_point = quant->zero_point->data[0];
    float thresh_float = score_thresh_val / scale + zero_point;
    if (thresh_float > 127.0f) thresh_float = 127.0f;
    if (thresh_float < -128.0f) thresh_float = -128.0f;
    score_thresh_int8[i] = (int8_t)thresh_float;
    xprintf("Idx %d (Tensor %d): Scale=%d/1000, ZP=%d, Int8Thresh=%d\n", i, indices[i], (int)(scale*1000), (int)zero_point, score_thresh_int8[i]);
}

int pass_count = 0;
float global_max_score = 0.0f;

for(int dims_cnt_1=0;dims_cnt_1<dim_total_size;dims_cnt_1++)
{
    //////conferen ok
    float maxScore = 0;
    int8_t val_int8 = 0;
    int thresh_idx = 0;
    int relative_idx = 0;
    int output_kpt_idx = 0;
    int relative_idx_kpt = 0;

    float tmp_result = 0;
    if(dims_cnt_1 < out_dim_size[0])//576
    {
        output_data_idx = idx_stride_8;
        thresh_idx = 0;
        relative_idx = dims_cnt_1;
        output_kpt_idx = idx_kpt_8;
        
        // If keypoints are concatenated (same tensor index for all strides), use absolute index
        if (idx_kpt_8 == idx_kpt_16) relative_idx_kpt = dims_cnt_1;
        else relative_idx_kpt = relative_idx;

        // Direct int8 access
        val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
        
        // Debug: Check max score
        // float current_score = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
        // if (current_score > global_max_score) global_max_score = current_score;

        if (val_int8 < score_thresh_int8[thresh_idx]) {
             // Debug print for first few anchors
             // if (dims_cnt_1 < 5 || (dims_cnt_1 > out_dim_size[0] && dims_cnt_1 < out_dim_size[0] + 5)) {
             //    xprintf("Skip: idx=%d, val=%d, thresh=%d\n", dims_cnt_1, val_int8, score_thresh_int8[thresh_idx]);
             // }
             continue; // Skip low confidence
        }

        maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
        
        // Debug print
        if (maxScore > 0.1f) {
            xprintf("Candidate: idx=%d, score=%d/1000\n", dims_cnt_1, (int)(maxScore*1000));
        }
    }
    else if(dims_cnt_1 < out_dim_size[1])//720
    {
        output_data_idx = idx_stride_16;
        thresh_idx = 1;
        relative_idx = dims_cnt_1 - out_dim_size[0];
        output_kpt_idx = idx_kpt_16;
        
        if (idx_kpt_8 == idx_kpt_16) relative_idx_kpt = dims_cnt_1;
        else relative_idx_kpt = relative_idx;

        val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
        // float current_score = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
        // if (current_score > global_max_score) global_max_score = current_score;

        if (val_int8 < score_thresh_int8[thresh_idx]) continue;

        maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0, output[output_data_idx]));
        if (maxScore > 0.1f) {
            xprintf("Candidate S16: idx=%d, score=%d/1000\n", dims_cnt_1, (int)(maxScore*1000));
        }
    }
    else 
    {
        output_data_idx = idx_stride_32;
        thresh_idx = 2;
        relative_idx = dims_cnt_1 - out_dim_size[1];
        output_kpt_idx = idx_kpt_32;

        if (idx_kpt_8 == idx_kpt_16) relative_idx_kpt = dims_cnt_1;
        else relative_idx_kpt = relative_idx;

        val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
        // float current_score = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
        // if (current_score > global_max_score) global_max_score = current_score;

        if (val_int8 < score_thresh_int8[thresh_idx]) continue;

        maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
        if (maxScore > 0.1f) {
            xprintf("Candidate S32: idx=%d, score=%d/1000\n", dims_cnt_1, (int)(maxScore*1000));
        }
    }
    // float maxScore = sigmoid(outputs_data_756_1[dims_cnt_2]);// the first four indexes are bbox information

    if (maxScore >= modelScoreThreshold)
    {
        pass_count++;
        box bbox;
    
        yolov8_pose_cal_xywh(dims_cnt_1, output, &bbox, anchor_756_2, stride_756_1,out_dim_size, box_indices );
        boxes.push_back(bbox);
        confidences.push_back(maxScore);
        
        struct_human_pose_17 kpts;
        for(int k = 0 ; k < 17 ; k++)
        {
            kpts.hpr[k].x = yolov8_pose_key_pts_dequant_value(relative_idx_kpt,k*3 , output[output_kpt_idx],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
            kpts.hpr[k].y = yolov8_pose_key_pts_dequant_value(relative_idx_kpt,k*3+1 , output[output_kpt_idx],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
            kpts.hpr[k].score = yolov8_pose_key_pts_dequant_value(relative_idx_kpt,k*3+2 , output[output_kpt_idx],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
        }
        kpts_vector.push_back(kpts);
    }
}
    xprintf("Boxes passing threshold: %d\n", pass_count);

	/**
	 * do nms
	 * **/

	std::vector<int> nms_result;
	yolov8_NMSBoxes(boxes, confidences, modelScoreThreshold, modelNMSThreshold, nms_result);
	std::vector<detection_yolov8_pose> results_yolov8_pose;
	for (int i = 0; i < nms_result.size(); i++)
	{
		if(!(MAX_TRACKED_YOLOV8_ALGO_RES-i))break;
		int idx = nms_result[i];

        float box_x = boxes[idx].x;
        float box_y = boxes[idx].y;
        float box_w = boxes[idx].w;
        float box_h = boxes[idx].h;

        // Fix clamping logic to be intersection-based
        float x1 = box_x;
        float y1 = box_y;
        float x2 = box_x + box_w;
        float y2 = box_y + box_h;

        // Debug large boxes
        if (box_w > tensor_w || box_h > tensor_h) {
            // xprintf("Large box detected: x=%d, y=%d, w=%d, h=%d\n", (int)box_x, (int)box_y, (int)box_w, (int)box_h);
        }

        if (x1 < 0) x1 = 0;
        if (y1 < 0) y1 = 0;
        if (x2 > tensor_w) x2 = tensor_w;
        if (y2 > tensor_h) y2 = tensor_h;

        // If box is completely outside, set to 0
        if (x1 >= x2) { x1 = 0; x2 = 0; }
        if (y1 >= y2) { y1 = 0; y2 = 0; }

        box_x = x1;
        box_y = y1;
        box_w = x2 - x1;
        box_h = y2 - y1;

        // Debug: Print box details before final scaling
        // xprintf("Box[%d]: x=%d, y=%d, w=%d, h=%d, score=%d/1000\n", i, (int)box_x, (int)box_y, (int)box_w, (int)box_h, (int)(confidences[idx]*1000));

        alg->dypr[i].bbox.x = (uint32_t)(box_x / (float)tensor_w * (float)img_w + 0.5f);
        alg->dypr[i].bbox.y = (uint32_t)(box_y / (float)tensor_h * (float)img_h + 0.5f);
        alg->dypr[i].bbox.width = (uint32_t)(box_w / (float)tensor_w * (float)img_w + 0.5f);
        alg->dypr[i].bbox.height = (uint32_t)(box_h / (float)tensor_h * (float)img_h + 0.5f);


		alg->dypr[i].confidence = confidences[idx];

		el_keypoint_t temp_el_keypoint;
		for(int k = 0 ; k < KEYPOINT_NUM ; k++)
		{
            float kpt_x = kpts_vector[idx].hpr[k].x;
            float kpt_y = kpts_vector[idx].hpr[k].y;
            float kpt_score = kpts_vector[idx].hpr[k].score;

            // Filter out low confidence keypoints (unreasonable ghost coordinates)
            float kpt_thresh = 0.15f;

            if (kpt_score < kpt_thresh) {
                kpt_x = 0;
                kpt_y = 0;
                kpt_score = 0.0f;
            }

			////resize to original image size
            if(kpt_x < 0) kpt_x = 0;
            if(kpt_y < 0) kpt_y = 0;

			if(kpt_x >= tensor_w) kpt_x = tensor_w;
			if(kpt_y >= tensor_h) kpt_y = tensor_h;

			alg->dypr[i].hpr[k].x = (uint32_t)(kpt_x / (float)tensor_w *(float)img_w + 0.5f);
			alg->dypr[i].hpr[k].y = (uint32_t)(kpt_y / (float)tensor_h * (float)img_h + 0.5f);
            alg->dypr[i].hpr[k].score = kpt_score;
			///resize to original image size

			/***set uart ouput format***/
			temp_el_keypoint.el_keypoint[k].score =  alg->dypr[i].hpr[k].score*100;
			temp_el_keypoint.el_keypoint[k].target =  k;
			temp_el_keypoint.el_keypoint[k].x = alg->dypr[i].hpr[k].x;
			temp_el_keypoint.el_keypoint[k].y =  alg->dypr[i].hpr[k].y;
		}

		temp_el_keypoint.el_box.score =  alg->dypr[i].confidence*100;
		temp_el_keypoint.el_box.target =  i;
		temp_el_keypoint.el_box.x = alg->dypr[i].bbox.x;
		temp_el_keypoint.el_box.y =  alg->dypr[i].bbox.y;
		temp_el_keypoint.el_box.w = alg->dypr[i].bbox.width;
		temp_el_keypoint.el_box.h = alg->dypr[i].bbox.height;

		el_keypoint_algo.emplace_front(temp_el_keypoint);

	}
	
}
