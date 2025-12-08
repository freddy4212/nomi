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

void yolov8_pose_cal_xywh(int j,TfLiteTensor* output[7], box *bbox, float* anchor_756_2,float *stride_756_1, int *out_dim_size )
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
                output_data_idx = 1;
                tmp_result = yolov8_pose_bbox_dequant_value(j, k*16+i,output[output_data_idx]);
            }
            else if(j < out_dim_size[1])//720
            {
                output_data_idx = 0;
                tmp_result = yolov8_pose_bbox_dequant_value(j - out_dim_size[0], k*16+i,output[output_data_idx]);
            }
            else 
            {
                output_data_idx = 5;
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

	int out_dim_total = 0;
	int numOutputs = static_interpreter->outputs_size();
	int out_dim_size_num = (numOutputs - 1) / 2;
	int out_dim_size[out_dim_size_num];
	for(int out_num = 0; out_num < out_dim_size_num; out_num++)
	{
		if(out_num==0)
		{
			output_data_idx = 4;
		}
		else if(out_num==1)
		{
			output_data_idx = 6;
		}
		else
		{
			output_data_idx = 2;
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
    int indices[] = {4, 6, 2}; // The output indices used below
    for(int i=0; i<3; i++) {
        TfLiteAffineQuantization* quant = (TfLiteAffineQuantization*)(output[indices[i]]->quantization.params);
        float scale = quant->scale->data[0];
        float zero_point = quant->zero_point->data[0];
        score_thresh_int8[i] = (int8_t)(score_thresh_val / scale + zero_point);
    }

	for(int dims_cnt_1=0;dims_cnt_1<dim_total_size;dims_cnt_1++)
	{
		//////conferen ok
		float maxScore = 0;
        int8_t val_int8 = 0;
        int thresh_idx = 0;
        int relative_idx = 0;

		float tmp_result = 0;
		if(dims_cnt_1 < out_dim_size[0])//576
		{
			output_data_idx = 4;
            thresh_idx = 0;
            relative_idx = dims_cnt_1;
            // Direct int8 access
            val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
            
            if (val_int8 < score_thresh_int8[thresh_idx]) continue; // Skip low confidence

			maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
		}
		else if(dims_cnt_1 < out_dim_size[1])//720
		{
			output_data_idx = 6;
            thresh_idx = 1;
            relative_idx = dims_cnt_1 - out_dim_size[0];
            
            val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
            if (val_int8 < score_thresh_int8[thresh_idx]) continue;

			maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0, output[output_data_idx]));
		}
		else 
		{
			output_data_idx = 2;
            thresh_idx = 2;
            relative_idx = dims_cnt_1 - out_dim_size[1];

            val_int8 = output[output_data_idx]->data.int8[relative_idx * output[output_data_idx]->dims->data[2]];
            if (val_int8 < score_thresh_int8[thresh_idx]) continue;

			maxScore = sigmoid(yolov8_pose_bbox_dequant_value(relative_idx, 0,output[output_data_idx]));
		}
		// float maxScore = sigmoid(outputs_data_756_1[dims_cnt_2]);// the first four indexes are bbox information

		if (maxScore >= modelScoreThreshold)
		{
			box bbox;
	
			yolov8_pose_cal_xywh(dims_cnt_1, output, &bbox, anchor_756_2, stride_756_1,out_dim_size );
			boxes.push_back(bbox);
			confidences.push_back(maxScore);
			
			struct_human_pose_17 kpts;
			for(int k = 0 ; k < 17 ; k++)
			{
				kpts.hpr[k].x = yolov8_pose_key_pts_dequant_value(dims_cnt_1,k*3 , output[3],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
				kpts.hpr[k].y = yolov8_pose_key_pts_dequant_value(dims_cnt_1,k*3+1 , output[3],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
				kpts.hpr[k].score = yolov8_pose_key_pts_dequant_value(dims_cnt_1,k*3+2 , output[3],anchor_756_2[dims_cnt_1 * 2 + 0],anchor_756_2[dims_cnt_1 * 2 + 1],stride_756_1[dims_cnt_1]);
			}
			kpts_vector.push_back(kpts);
		}
	}

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

        if(box_x < 0) box_x = 0;
        if(box_y < 0) box_y = 0;
        if(box_w < 0) box_w = 0;
        if(box_h < 0) box_h = 0;

        if(box_x >= tensor_w) box_x = tensor_w;
        if(box_y >= tensor_h) box_y = tensor_h;
        if(box_w >= tensor_w) box_w = tensor_w;
        if(box_h >= tensor_h) box_h = tensor_h;

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
