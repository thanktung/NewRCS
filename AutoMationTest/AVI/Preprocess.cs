using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Emgu.CV;
using Emgu.CV.UI;
using Emgu.CV.Structure;
using Emgu.CV.Util;
using Emgu.CV.CvEnum;
using System.Drawing.Drawing2D;
using EmgucvLib;
using EmgucvExLib;
using System.Drawing;
using Emgu.CV.OCR;
using System.Collections;

namespace AutoMationTest.AVI
{
  public   class Preprocess
    {
        //灰度化
        public Mat PicToGray(Mat inputMat)
        {
            ToGray gray = new ToGray();
            Mat OutPutGrayMat = gray.Action(inputMat);
            return OutPutGrayMat;
        }
        //彩色图像处理--白平衡
        //public Mat ToBalanceWhite(Mat inputMat)
        //{
        //    Mat BalanceMat = new Mat();
        //    CvInvoke.BalanceWhite(inputMat, BalanceMat, Emgu.CV.CvEnum.WhiteBalanceMethod.Simple, 0, 255, 0, 255);
        //    return BalanceMat;
        //}

        // Mark_ROI截取图像
        public Mat Mark_ROI(Mat input, Rectangle Roi)
        {
            Mat roiMat = new Mat(input, Roi);
            return roiMat;
        }

        public enum ColorChannel
        {
            R,
            G,
            B,
            H,
            S,
            V,
        }
        public static Mat SelectColorChannel(Mat inputMat, ColorChannel channel)
        {
            Mat opMat = inputMat.Clone();
            if (channel == ColorChannel.H || channel == ColorChannel.S || channel == ColorChannel.V)
            {
                CvInvoke.CvtColor(opMat, opMat, Emgu.CV.CvEnum.ColorConversion.Bgr2Hsv);
            }
            VectorOfMat Mats = new VectorOfMat();
            CvInvoke.Split(opMat, Mats);
            Mat result = null;
            switch (channel)
            {
                case ColorChannel.R:
                    result = Mats[2].Clone();
                    break;
                case ColorChannel.G:
                    result = Mats[1].Clone();
                    break;
                case ColorChannel.B:
                    result = Mats[0].Clone();
                    break;
                case ColorChannel.H:
                    result = Mats[0].Clone();
                    break;
                case ColorChannel.S:
                    result = Mats[1].Clone();
                    break;
                case ColorChannel.V:
                    result = Mats[2].Clone();
                    break;
                default:
                    throw new Exception("获取的颜色通道有误");
            }
            opMat.Dispose();
            Mats.Dispose();
            return result;
        }

        //灰度平衡
        public Mat BalanceGray(Mat inputMat)
        {
            EqualizeHist equalizeHist = new EqualizeHist();
            Mat equalizeMat = equalizeHist.Action(inputMat);
            return equalizeMat;
        }
        //可调阈值化
        public static Mat Action(Mat inputMat, int low, int high)
        {
            if (inputMat.NumberOfChannels != 1)
            {
                throw new Exception("请确认输入图像为单通道图像");
            }

            low = low == 0 ? -1 : low;
            high = high == 255 ? 256 : high;
            Mat OperationMat = inputMat.Clone();
            Mat threshLowMat = new Mat();
            CvInvoke.Threshold(OperationMat.Clone(), threshLowMat, low, 255, Emgu.CV.CvEnum.ThresholdType.Binary);
            Mat threshHighMat = new Mat();
            CvInvoke.Threshold(OperationMat.Clone(), threshHighMat, high, 255, Emgu.CV.CvEnum.ThresholdType.Binary);

            Image<Gray, byte> threshLowImg = threshLowMat.ToImage<Gray, byte>();
            Image<Gray, byte> threshHighImg = threshHighMat.ToImage<Gray, byte>();
            Image<Gray, byte> XorImg = threshLowImg.Xor(threshHighImg);

            return XorImg.Mat;
        }

        //形态学操作
        public Mat PicToMorphology(Mat inputMat, ElementShape shape, Size elementSize, MorphOp opMode, int Num)
        {
            //Mat MorphologyMat=EmcvInvoke.MorphologyEx(inputMat, shape, elementSize, opMode);
            //return MorphologyMat;
            if (inputMat.NumberOfChannels != 1)
            {
                throw new Exception("图像不是单通道");
            }

            Mat OperationMat = inputMat.Clone();
            Mat element = CvInvoke.GetStructuringElement(shape, elementSize, new Point(-1, -1));
            Mat MorphologyMat = new Mat();
            CvInvoke.MorphologyEx(OperationMat, MorphologyMat, opMode, element, new Point(-1, -1), Num, BorderType.Default, new Emgu.CV.Structure.MCvScalar(0,0,0));
            OperationMat.Dispose();
            element.Dispose();
            return MorphologyMat;
        }

        //边缘提取
        public VectorOfVectorOfPoint FindContours(Mat inputMat, RetrType retrType, ChainApproxMethod chainApproxMethod)
        {
            //Mat OperationMat = inputMat.Clone();
            if (inputMat.NumberOfChannels != 1)
                CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            VectorOfVectorOfPoint contours = new VectorOfVectorOfPoint();
            CvInvoke.FindContours(inputMat, contours, null, retrType, chainApproxMethod);
            return contours;
        }

        //绘画边缘
        public Mat DrawContours(Mat inputMat, VectorOfVectorOfPoint contours)
        {
            Mat mask = inputMat.ToImage<Gray, byte>().CopyBlank().Mat;
            CvInvoke.DrawContours(mask, contours, -1, new MCvScalar(255), 1);
            return mask;
        }

        //填充
        public Mat FillMat(Mat inputMat, VectorOfVectorOfPoint contours)
        {
            Mat result = new Mat(inputMat.Size, DepthType.Cv8U, 1);
            result.SetTo(new MCvScalar(0));
            for (int num = 0; num < contours.Size; num++)
            {
                CvInvoke.DrawContours(result, contours, num , new MCvScalar(255), -1, LineType.EightConnected);
                MCvMoments mo = CvInvoke.Moments(contours[num]);
               int x=Convert.ToInt32(mo.GravityCenter.X);
               int y = Convert.ToInt32(mo.GravityCenter.Y);
               CvInvoke.Circle(result, new Point(x, y), 10, new MCvScalar(0,0,255), 2, LineType.EightConnected);

            }
            return result;
        }

        //基础阈值
        public static Mat PicToThreshold(Mat inputMat, int threshold, Emgu.CV.CvEnum.ThresholdType type)
        {
            Mat output = new Mat();
            CvInvoke.Threshold(inputMat, output, threshold, 255, type);
            return output;
        }
        //查找最大面积
        public double GetMaxArea(VectorOfVectorOfPoint contours)
        {
            int ksize = contours.Size;
            double maxarea = double.MinValue;
            for (int i = 0; i < ksize; i++)
            {
                VectorOfPoint contour = contours[i];
                double area = CvInvoke.ContourArea(contour);
                if (area > maxarea)
                {
                    maxarea = area;
                }
            }
            return maxarea;
        }

        //查找最大長度
        public double GetMaxLength(VectorOfVectorOfPoint contours)
        {
            int ksize = contours.Size;
            //double maxarea = double.MinValue;
            ArrayList alt = new ArrayList();

            for (int i = 0; i < ksize; i++)
            {
                VectorOfPoint contour = contours[i];
                double length = CvInvoke.ArcLength(contour, false);
                alt.Add(length);
            }

            alt.Sort();

            return Convert.ToDouble(alt[alt.Count-1]);
        }
        //筛选连通域图像
        public VectorOfVectorOfPoint GetSelectArea(VectorOfVectorOfPoint contours, double low, double high,string type)
        {
            VectorOfVectorOfPoint user_Contours = new VectorOfVectorOfPoint();
            int ksize = contours.Size;
            for (int i = 0; i < ksize; i++)
            {
                VectorOfPoint contour = contours[i];
                double area=0;
                if (type == "ares")
                {
                    area = CvInvoke.ContourArea(contour);
                }
                else
                {
                    area = CvInvoke.ArcLength(contour, false);
                }

                if (area >= low && area <= high)
                {
                    user_Contours.Push(contour);
                }
            }
            return user_Contours;
        }

        //图像缩放
        public Mat ImageResize(Mat InputMat, double num_X, double num_Y)
        {
            Mat dst = new Mat();
            CvInvoke.Resize(InputMat, dst, new Size(0, 0), num_X, num_Y, Emgu.CV.CvEnum.Inter.Cubic);
            return dst;
        }
        //旋转，并且尺寸改变
        public Mat RotateWithSizeSwitch(Mat inputMat, double Angle)
        {
            Mat OperationMat = inputMat.Clone();
            Image<Bgr, byte> img = OperationMat.ToImage<Bgr, byte>();
            img = img.Rotate(Angle, new Bgr(0, 0, 0), false);
            return img.Mat;

        }

        //模板匹配
        public static Point TempMatch(Mat srcMat, Mat tempMat)
        {
            try
            {
                Mat srcOperateMat = srcMat.Clone();
                Mat tempOperateMat = tempMat.Clone();
                if (srcMat.NumberOfChannels != 1) CvInvoke.CvtColor(srcOperateMat, srcOperateMat, Emgu.CV.CvEnum.ColorConversion.Bgr2Gray);
                if (tempMat.NumberOfChannels != 1) CvInvoke.CvtColor(tempOperateMat, tempOperateMat, Emgu.CV.CvEnum.ColorConversion.Bgr2Gray);

                int result_Rows = srcOperateMat.Rows - tempOperateMat.Rows + 1;
                int result_Cols = srcOperateMat.Cols - tempOperateMat.Cols + 1;
                Mat result = new Mat(result_Rows, result_Cols, Emgu.CV.CvEnum.DepthType.Cv32F, 1);

                CvInvoke.MatchTemplate(srcOperateMat, tempOperateMat, result, Emgu.CV.CvEnum.TemplateMatchingType.SqdiffNormed);

                double minValue = 0, maxValue = 0;
                Point minLocation = Point.Empty, maxLocation = Point.Empty;
                CvInvoke.MinMaxLoc(result, ref minValue, ref maxValue, ref minLocation, ref maxLocation);

                Point outPt = new Point(minLocation.X + tempMat.Width / 2, minLocation.Y + tempMat.Height / 2);

                srcOperateMat.Dispose();
                tempOperateMat.Dispose();
                result.Dispose();

                return outPt;
            }
            catch (Exception ex)
            {
                throw ex;
            }

        }

    }
}
