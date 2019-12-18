using Color_Lib;
using Emgu.CV;
using Emgu.CV.CvEnum;
using Emgu.CV.Structure;
using Emgu.CV.Util;
using EmgucvExLib;
using EmgucvLib;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using VI_Lib;

namespace WindowsTest
{
    public static class Emgucv_Func_Lib
    {
        /// <summary>
        ///  Channel通道抽取類型
        /// </summary>
        public enum ColorChannel
        {
            R,
            G,
            B,
            H,
            S,
            V,
            RG,
            RB,
            GR,
            GB,
            BR,
            BG,
        }

        /// <summary>
        /// 攫取图像ROI(bitmap類型圖片)
        /// </summary>
        /// <param name="bmp">原始图像</param>
        /// <param name="rect">攫取范围</param>
        /// <returns></returns>
        public static Bitmap BitmapCut(Bitmap bmp_1, Rectangle rect)
        {
            Bitmap bmp = bmp_1.Clone() as Bitmap;
            if (bmp == null)
                return null;

            int w = bmp.Width;
            int h = bmp.Height;

            if (rect.X >= w || rect.Y >= h)
                return null;

            if (rect.X + rect.Width > w)
                rect.Width = w - rect.X;
            if (rect.Y + rect.Height > h)
                rect.Height = h - rect.Y;

            try
            {
                Bitmap bmpOut = new Bitmap(rect.Width, rect.Height, System.Drawing.Imaging.PixelFormat.Format24bppRgb);

                Graphics g = Graphics.FromImage(bmpOut);

                g.DrawImage(bmp, new Rectangle(0, 0, rect.Width, rect.Height), new Rectangle(rect.X, rect.Y, rect.Width, rect.Height), GraphicsUnit.Pixel);

                bmp.Dispose();//Clone 參數要釋放,否則資源佔用
                bmp = null;
                return bmpOut.Clone() as Bitmap;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        ///  Mark_ROI截取图像(Mat 類型圖片)
        /// </summary>
        /// <param name="input">刷如圖像</param>
        /// <param name="Roi">感興趣區域(ROI)</param>
        /// <returns></returns>
        public static Mat Mark_ROI(Mat input, Rectangle Roi)
        {
            Mat roiMat = new Mat(input, Roi);

            input.Dispose();

            return roiMat;
        }

        /// <summary>
        /// Bitmap 2 Mat
        /// </summary>
        /// <param name="bmp">輸入圖像</param>
        /// <returns></returns>
        public static Mat Bmp2Mat(Bitmap bmp)
        {
            Bitmap src = bmp.Clone() as Bitmap;
            Image<Bgr, byte> image = new Image<Bgr, byte>(src);
            src.Dispose();
            src = null;
            return image.Mat;
        }

        /// <summary>
        /// Bitmap 2 Mat
        /// </summary>
        /// <param name="bmp">輸入圖像</param>
        /// <returns></returns>
        public static Mat ImagePath2Mat(string path)
        {
            Bitmap bmp = new Bitmap(@path);
            Bitmap src = bmp.Clone() as Bitmap;
            Image<Bgr, byte> image = new Image<Bgr, byte>(src);
            src.Dispose();
            src = null;
            bmp.Dispose();
            bmp = null;
            return image.Mat;
        }

        /// <summary>
        /// 圖像通道分割
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="channel">分割項</param>
        /// <returns></returns>
        public static Mat Color_Split_Func(Mat inputMat, ColorChannel channel)
        {
            Mat result = null;
            Mat inputMat_1 = inputMat.Clone();
            if (channel == ColorChannel.RG)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.R);
                mat2 = Channel(inputMat_1, ColorChannel.G);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else if (channel == ColorChannel.RB)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.R);
                mat2 = Channel(inputMat_1, ColorChannel.B);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else if (channel == ColorChannel.GR)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.G);
                mat2 = Channel(inputMat_1, ColorChannel.R);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else if (channel == ColorChannel.GB)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.G);
                mat2 = Channel(inputMat_1, ColorChannel.B);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else if (channel == ColorChannel.BR)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.B);
                mat2 = Channel(inputMat_1, ColorChannel.R);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else if (channel == ColorChannel.BG)
            {
                Mat mat1 = new Mat();
                Mat mat2 = new Mat();
                mat1 = Channel(inputMat_1, ColorChannel.B);
                mat2 = Channel(inputMat_1, ColorChannel.G);
                Image<Rgb, byte> Pic = mat1.ToImage<Rgb, byte>().Sub(mat2.ToImage<Rgb, byte>());
                result = Pic.ToUMat().ToMat(Emgu.CV.CvEnum.AccessType.ReadWrite);
            }
            else
            {
                result = Channel(inputMat_1, channel);
            }
            inputMat_1.Dispose();
            return result;
        }

        public static Mat Channel(Mat inputMat, ColorChannel channel)
        {
            Mat result = null;
            Mat opMat = inputMat.Clone();
            if (channel == ColorChannel.H || channel == ColorChannel.S || channel == ColorChannel.V)
            {
                CvInvoke.CvtColor(opMat, opMat, Emgu.CV.CvEnum.ColorConversion.Bgr2Hsv);
            }
            VectorOfMat Mats = new VectorOfMat();
            CvInvoke.Split(opMat, Mats);

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

        /// <summary>
        /// 顏色提取
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="blue_min">B 最小值</param>
        /// <param name="green_min">G 最小值</param>
        /// <param name="red_min">R 最小值</param>
        /// <param name="blue_max">B 最大值</param>
        /// <param name="green_max">G 最大值</param>
        /// <param name="red_max">R 最大值</param>
        /// <returns></returns>
        public static Mat Color_Extract(Mat inputMat, double blue_min, double green_min, double red_min, double blue_max, double green_max, double red_max)
        {
            Mat src = inputMat.Clone();
            Image<Bgr, byte> bgr_img = src.ToImage<Bgr, byte>();
            Bgr min = new Bgr(blue_min, green_min, red_min);
            Bgr max = new Bgr(blue_max, green_max, red_max);
            Image<Gray, byte> result = bgr_img.InRange(min, max);
            src.Dispose();
            return result.Mat;
        }

        /// <summary>
        /// 灰度化
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <returns></returns>
        public static Mat PicToGray(Mat inputMat)
        {
            Mat src = inputMat.Clone();
            Mat dst = new Mat();
            CvInvoke.CvtColor(src, dst, ColorConversion.Bgr2Gray, 0);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// 灰度平衡
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <returns></returns>
        public static Mat BalanceGray(Mat inputMat)
        {
            Mat src = inputMat.Clone();
            Mat dst = new Mat();
            CvInvoke.EqualizeHist(src, dst);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// 自適應二值畫
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="size">像素邻域的大小,用来计算一个像素的阈值</param>
        /// <param name="param">均值或高斯加权平均值所需要减去的一个常数，类似一个人工干预的阈值调整</param>
        /// <returns></returns>
        public static Mat AdaptThreshold(Mat inputMat, int size, double param)
        {
            Mat src = inputMat.Clone();
            Mat dst = new Mat();
            CvInvoke.AdaptiveThreshold(src, dst, 255.0, AdaptiveThresholdType.MeanC, ThresholdType.BinaryInv, size, param);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// 可調二值畫
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="low">最小值</param>
        /// <param name="high">最大值</param>
        /// <returns></returns>
        public static Mat ThresholdValue(Mat inputMat, int low, int high)
        {
            low = low == 0 ? -1 : low;
            high = high == 255 ? 256 : high;
            Mat OperationMat = inputMat.Clone();
            Mat threshLowMat = new Mat();
            CvInvoke.Threshold(OperationMat, threshLowMat, low, 255, Emgu.CV.CvEnum.ThresholdType.Binary);
            Mat threshHighMat = new Mat();
            CvInvoke.Threshold(OperationMat, threshHighMat, high, 255, Emgu.CV.CvEnum.ThresholdType.Binary);

            Image<Gray, byte> threshLowImg = threshLowMat.ToImage<Gray, byte>();
            Image<Gray, byte> threshHighImg = threshHighMat.ToImage<Gray, byte>();
            Image<Gray, byte> XorImg = threshLowImg.Xor(threshHighImg);
            OperationMat.Dispose();
            threshHighMat.Dispose();
            Mat TEMP = XorImg.Clone().Mat;
            XorImg.Dispose();
            XorImg = null;
            GC.Collect();
            return TEMP;
            //return XorImg.Mat;
        }

        /// <summary>
        /// hsb 二值畫(基础阈值)
        /// </summary>
        /// <param name="input">輸入圖像</param>
        /// <param name="threshold">阈值</param>
        /// <param name="type">阈值函数标识符类型</param>
        /// <returns></returns>
        public static Mat hsb_ThresholdValue(Mat input, int threshold, Emgu.CV.CvEnum.ThresholdType type)
        {
            Mat src = input.Clone();
            if (src.NumberOfChannels != 1)
                CvInvoke.CvtColor(src, src, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            CvInvoke.Threshold(src, output, threshold, 255, type);
            src.Dispose();
            return output;
        }

        /// <summary>
        /// k_Size中值滤波
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="ksize"></param>
        /// <returns></returns>
        public static Mat Median_Filter_Func(Mat inputMat, int ksize)
        {
            //if (inputMat.NumberOfChannels != 1)
            //    CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.MedianBlur(src, output, ksize);
            src.Dispose();
            return output;
        }

        /// <summary>
        /// 均值滤波
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="width"></param>
        /// <param name="height"></param>
        /// <returns></returns>
        public static Mat Blur_width(Mat inputMat, int width, int height)
        {
            if (inputMat.NumberOfChannels != 1)
                CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.Blur(src, output, new Size(width, height), new Point(-1, -1), Emgu.CV.CvEnum.BorderType.Default);
            src.Dispose();
            return output;
        }

        /// <summary>
        /// 高斯滤波
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="width"></param>
        /// <param name="height"></param>
        /// <returns></returns>
        public static Mat gauss_width(Mat inputMat, int width, int height, int SigmaX)
        {
            if (inputMat.NumberOfChannels != 1)
                CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.GaussianBlur(src, output, new Size(width, height), SigmaX);
            src.Dispose();
            return output;
        }

        /// <summary>
        /// 双边滤波
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="d"></param>
        /// <param name="color"></param>
        /// <param name="space"></param>
        /// <returns></returns>
        public static Mat Bilateral_d(Mat inputMat, int d, int color, int space)
        {
            if (inputMat.NumberOfChannels != 1)
                CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.BilateralFilter(src, output, d, color, space);
            src.Dispose();
            return output;
        }

        /// <summary>
        /// 方框滤波
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="width"></param>
        /// <param name="height"></param>
        /// <returns></returns>
        public static Mat Box_width(Mat inputMat, int width, int height)
        {
            if (inputMat.NumberOfChannels != 1)
                CvInvoke.CvtColor(inputMat, inputMat, ColorConversion.Bgr2Gray);
            Mat output = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.BoxFilter(src, output, Emgu.CV.CvEnum.DepthType.Cv8U, new Size(width, height), new Point(-1, -1));
            src.Dispose();
            return output;
        }

        /// <summary>
        /// 形態學操作
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="shape">枚举类型</param>
        /// <param name="elementSize">结构元素大小</param>
        /// <param name="opMode">操作类型</param>
        /// <param name="Num">迭代次数</param>
        /// <returns></returns>
        public static Mat PicToMorphology(Mat inputMat, ElementShape shape, Size elementSize, MorphOp opMode, int Num)
        {
            if (inputMat.NumberOfChannels != 1)
            {
                throw new Exception("图像不是单通道");
            }

            Mat OperationMat = inputMat.Clone();
            Mat element = CvInvoke.GetStructuringElement(shape, elementSize, new Point(-1, -1));
            Mat MorphologyMat = new Mat();
            CvInvoke.MorphologyEx(OperationMat, MorphologyMat, opMode, element, new Point(-1, -1), Num, BorderType.Default, new Emgu.CV.Structure.MCvScalar(0, 0, 0));
            OperationMat.Dispose();
            element.Dispose();
            return MorphologyMat;
        }

        /// <summary>
        /// 灰度直方圖
        /// </summary>
        /// <param name="inputMat"></param>
        /// <returns></returns>
        public static Bitmap DrawGrayHist(Mat inputMat)
        {
            Mat OperationMat = inputMat.Clone();
            int[] data = Histogram_Lib.Histogram.GetData(OperationMat);
            int Max = Histogram_Lib.Histogram.GetMax(data);
            return DrawHist(data, Max);
        }

        private static Bitmap DrawHist(int[] data, int Max)
        {
            Bitmap hist = new Bitmap(data.Length, 100);
            double Scale = Max / 100.0;
            using (Graphics g = Graphics.FromImage(hist))
            {
                g.Clear(Color.White);
                for (int num = 0; num < data.Length; num++)
                {
                    int Value = (int)(data[num] / Scale);

                    g.DrawLine(Pens.Black, new Point(num, hist.Height), new Point(num, hist.Height - Value - 1));
                }
            }
            return hist;
        }

        /// <summary>
        /// Canny 边缘检测
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="low">第一滞后阈值</param>
        /// <param name="high">第二滞后阈值</param>
        /// <returns></returns>
        public static Mat Canny(Mat inputMat, int low, int high)
        {
            Mat image = inputMat.Clone();
            Mat edges = new Mat();
            CvInvoke.Canny(image, edges, (double)low, (double)high, 3, false);
            image.Dispose();
            return edges;
        }

        /// <summary>
        /// Sobel 边缘检测
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="scale">可选的比例因子的计算导数值</param>
        /// <param name="delta">表示结果存入输出图像即dst，之前的delta 值</param>
        /// <returns></returns>
        ///
        public static Mat Sobel(Mat inputMat, int scale, int delta)
        {
            Mat dst = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.Sobel(src, dst, Emgu.CV.CvEnum.DepthType.Default, scale, delta);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// Laplace邊緣檢測
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="size">二阶导数滤波器的孔径尺寸，必须为正基数</param>
        /// <returns></returns>
        public static Mat Laplace(Mat inputMat, int size)
        {
            Mat dst = new Mat();
            Mat src = inputMat.Clone();
            CvInvoke.Laplacian(src, dst, Emgu.CV.CvEnum.DepthType.Default, size);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// 邊緣提取
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="retrType">提取類型(标识符)</param>
        /// <param name="chainApproxMethod"></param>
        /// <returns></returns>
        public static VectorOfVectorOfPoint FindContours(Mat inputMat, RetrType retrType, ChainApproxMethod chainApproxMethod)
        {
            VectorOfVectorOfPoint contours = new VectorOfVectorOfPoint();
            Mat src = inputMat.Clone();
            CvInvoke.FindContours(src, contours, null, retrType, chainApproxMethod);
            src.Dispose();
            return contours;
        }

        /// <summary>
        /// 繪畫提取的邊緣
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="contours">所有邊緣(連通域)</param>
        /// <returns></returns>
        public static Mat DrawContours(Mat inputMat, VectorOfVectorOfPoint contours)
        {
            Mat src = inputMat.Clone();
            Mat mask = src.ToImage<Gray, byte>().CopyBlank().Mat;
            CvInvoke.DrawContours(mask, contours, -1, new MCvScalar(255), 1);
            src.Dispose();
            //src = null;
            return mask;
        }

        /// <summary>
        /// 查找連通域最大面积
        /// </summary>
        /// <param name="contours"></param>
        /// <returns></returns>
        public static double GetMaxArea(VectorOfVectorOfPoint contours)
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

        /// <summary>
        /// 查找連通域最大長度
        /// </summary>
        /// <param name="contours"></param>
        /// <returns></returns>
        public static double GetMaxLength(VectorOfVectorOfPoint contours)
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

            return Convert.ToDouble(alt[alt.Count - 1]);
        }

        /// <summary>
        /// 筛选连通域图像
        /// </summary>
        /// <param name="contours"></param>
        /// <param name="low">最小值</param>
        /// <param name="high">最大值</param>
        /// <param name="type">篩選類型(面積:ares Or 周長)</param>
        /// <returns></returns>
        public static VectorOfVectorOfPoint Contour_Filter_Func(VectorOfVectorOfPoint contours, double low, double high, string type, ref string info_message)
        {
            VectorOfVectorOfPoint user_Contours = new VectorOfVectorOfPoint();
            int ksize = contours.Size;
            for (int i = 0; i < ksize; i++)
            {
                VectorOfPoint contour = contours[i];
                double area = 0;
                if (type == "ares")
                {
                    area = CvInvoke.ContourArea(contour);
                    info_message += area.ToString() + ",";
                }
                else
                {
                    area = CvInvoke.ArcLength(contour, false);
                    info_message += area.ToString() + ",";
                }

                if (area >= low && area <= high)
                {
                    user_Contours.Push(contour);
                }
            }
            return user_Contours;
        }

        /// <summary>
        /// 遍歷每個連通域面積&周長
        /// </summary>
        /// <param name="vvp"></param>
        /// <returns></returns>
        public static string GetContourInfo(VectorOfVectorOfPoint vvp)
        {
            string info = "Contours_Count:" + vvp.Size.ToString() + " || ";
            for (int mm = 0; mm < vvp.Size; mm++)
            {
                VectorOfPoint contour = vvp[mm];
                //double area = 0;
                double area = CvInvoke.ContourArea(contour);
                double length = CvInvoke.ArcLength(contour, false);
                info += "Contour_" + (mm + 1).ToString() + ":Ares:" + area.ToString() + " Length:" + length.ToString() + " || ";
            }
            return info;
        }

        /// <summary>
        /// 連通域橢圓擬合
        /// </summary>
        /// <param name="inputMat">連通域圖像</param>
        /// <param name="contours">連通域</param>
        /// <param name="info_message">擬合信息</param>
        /// <returns></returns>
        public static Mat FitEllipse_Func(Mat inputMat, VectorOfVectorOfPoint contours, ref string info_message)
        {
            if (contours.Size < 1)
            {
                info_message = "contours is null";
                return null;
            }
            Mat src = inputMat.Clone();
            Image<Bgr, byte> dst = src.ToImage<Bgr, byte>();
            info_message = "Fitting_ellipse_Count:" + contours.Size.ToString() + " || ";
            for (int i = 0; i < contours.Size; i++)
            {
                VectorOfPoint contour = contours[i];
                RotatedRect fit_ell = CvInvoke.FitEllipse(contour);
                Ellipse ell = new Ellipse(fit_ell);
                dst.Draw(ell, new Bgr(0, 255, 0), 2);
                info_message += "Ellipse_" + (i + 1).ToString() + ":Center:" + fit_ell.Center.X + "," + fit_ell.Center.Y + " Angle:" + fit_ell.Angle + " || ";
            }
            src.Dispose();
            return dst.Mat;
        }

        /// <summary>
        /// 連通域矩形擬合
        /// </summary>
        /// <param name="inputMat">連通域圖像</param>
        /// <param name="contours">連通域</param>
        /// <param name="info_message">擬合信息</param>
        /// <returns></returns>
        public static Mat FitRectangle_Func(Mat inputMat, VectorOfVectorOfPoint contours, ref string info_message)
        {
            if (contours.Size < 1)
            {
                info_message = "contours is null";
                return null;
            }
            Mat src = inputMat.Clone();
            Image<Bgr, byte> dst = src.ToImage<Bgr, byte>();
            info_message = "Fitting_Rectangle_Count:" + contours.Size.ToString() + " || ";

            for (int i = 0; i < contours.Size; i++)
            {
                VectorOfPoint contour = contours[i];
                RotatedRect fit_ell = CvInvoke.FitEllipse(contour);
                dst.Draw(fit_ell, new Bgr(0, 255, 0), 2);
                info_message += "Rectangle_" + (i + 1).ToString() + ":Center:" + fit_ell.Center.X + "," + fit_ell.Center.Y + " Angle:" + fit_ell.Angle + " || ";
            }
            src.Dispose();
            return dst.Mat;
        }

        /// <summary>
        /// 連通域直線擬合
        /// </summary>
        /// <param name="inputMat">連通域圖像</param>
        /// <param name="contours">連通域</param>
        /// <param name="DistType">DistType類型</param>
        /// <param name="info_message">擬合信息</param>
        /// <returns></returns>
        public static Mat FitLine_Func(Mat inputMat, VectorOfVectorOfPoint contours, int DistType, ref string info_message)
        {
            if (contours.Size < 1)
            {
                info_message = "contours is null";
                return null;
            }
            Mat src = inputMat.Clone();
            Image<Bgr, byte> dst = src.ToImage<Bgr, byte>();
            info_message = "Fitting_Line_Count:" + contours.Size.ToString() + " || ";

            for (int i = 0; i < contours.Size; i++)
            {
                VectorOfPoint contour = contours[i];
                VectorOfFloat line = new VectorOfFloat();// 创建VectorOfFloat 类型作为直线输出数据。

                if (DistType == 0)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.User, 0, 0.01, 0.01);
                }
                else if (DistType == 1)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.L1, 0, 0.01, 0.01);
                }
                else if (DistType == 2)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.L2, 0, 0.01, 0.01);
                }
                else if (DistType == 3)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.C, 0, 0.01, 0.01);
                }
                else if (DistType == 4)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.L12, 0, 0.01, 0.01);
                }
                else if (DistType == 5)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.Fair, 0, 0.01, 0.01);
                }
                else if (DistType == 6)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.Welsch, 0, 0.01, 0.01);
                }
                else if (DistType == 7)
                {
                    CvInvoke.FitLine(contour, line, Emgu.CV.CvEnum.DistType.Huber, 0, 0.01, 0.01);
                }
                //指定参数进行线性拟合。
                float[] p = line.ToArray();//提取数据。

                double theta = Math.Atan(p[1] / p[0]);//获得直线的角度theta
                PointF p1 = new PointF(p[2], p[3]);//获得直线的中心点。//** 下面通过角度， 中心点， 分别计算直线与x=0 和x=dst.Height 这两条直线角点** //
                float x = (float)(p[2] + p[3] / Math.Tan(theta));
                float y = 0;
                float y1 = dst.Height;
                float x1 = (float)(p[2] - (dst.Height - p[3]) /
                Math.Tan(theta));
                PointF p2 = new PointF(x, y);//得到直线与x=0 交点坐标
                PointF p3 = new PointF(x1, y1);//得到直线与y=0 交点坐标。
                dst.Draw(new LineSegment2DF(p2, p3), new Bgr(0, 255, 0), 3);//绘制拟合直线。

                LineSegment2DF line_1 = new LineSegment2DF(p2, p3);
                double angle = 0;
                if (line_1.P1.X == line_1.P2.X)
                {
                    angle = 90;
                }
                else if (line_1.P1.Y == line_1.P2.Y)
                {
                    angle = 0;
                }
                else
                {
                    PointF Start = new PointF((p1.X - 100), p1.Y);
                    PointF End = new PointF((p1.X + 100), p1.Y);
                    LineSegment2DF line_NEW = new LineSegment2DF(Start, End);
                    angle = line_1.GetExteriorAngleDegree(line_NEW);
                }
                info_message += "Line_" + (i + 1).ToString() + ":Center:" + p1.X + "," + p1.Y + " Angle:" + angle + " || ";

                dst.Draw(new CircleF(p1, 3), new Bgr(255, 255, 255), 3);//绘制中心点坐标。
            }
            src.Dispose();
            return dst.Mat;
        }

        /// <summary>
        /// 獲取連通域的矩
        /// </summary>
        /// <param name="inputMat">連通域圖像</param>
        /// <param name="contours">連通域</param>
        /// <param name="info_message">擬合信息</param>
        /// <returns></returns>
        public static Mat VVP_Moments(Mat inputMat, VectorOfVectorOfPoint contours, ref string info_message)
        {
            int ksize = contours.Size;//得到独立轮廓的个数（连通域）。
            if (ksize == 0)
            {
                info_message = "Please extract the connected domain before performing this operation ";
                return null;
            }
            Mat src = inputMat.Clone();
            info_message = "Contours_Count:" + ksize.ToString() + " || ";
            double[] m00 = new double[ksize];//存储所有轮廓的M00
            double[] m10 = new double[ksize];//存储所有轮廓的M10
            double[] m01 = new double[ksize];//存储所有轮廓的M01
            Point[] Gravity = new Point[ksize];//存储所有轮廓的重心
            MCvMoments[] hu = new MCvMoments[ksize];//创建McvMoments
            //Mat scr = m_CurrentMat.Clone();
            Image<Bgr, byte> scr = src.ToImage<Bgr, byte>();
            for (int i = 0; i < ksize; i++)
            {
                VectorOfPoint contour = contours[i]; //创建独立轮廓
                hu[i] = CvInvoke.Moments(contour, false);//得到轮廓矩
                m00[i] = hu[i].M00;//得到M00。
                m10[i] = hu[i].M10;//得到M10。
                m01[i] = hu[i].M01;//得到M01。
                double X = m10[i] / m00[i];//得到中心的X 坐标。
                double Y = m01[i] / m00[i];//得到中心的Y 坐标。
                Gravity[i] = new Point((int)X, (int)Y);//得到中心心的位置。
            }
            int mm = 0;
            foreach (Point cent in Gravity)//遍历所有的轮廓的重心
            {
                CvInvoke.Circle(scr, cent, 2, new MCvScalar(0, 0, 255), 2);//画出中心心的位置
                info_message += "contour_" + (++mm).ToString() + ":Center:" + cent.X + "," + cent.Y + " || ";
            }
            src.Dispose();
            return scr.Clone().Mat;
        }

        /// <summary>
        /// 角點檢測
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="thread_valueref">二值畫閾值</param>
        /// <param name="info_message">角點信息</param>
        /// <returns></returns>
        public static Mat CornerHarris_Func(Mat inputMat, int thread_valueref, ref string info_message)
        {
            Mat gray_scr = inputMat.Clone();
            CvInvoke.CornerHarris(gray_scr, gray_scr, 3);//灰度图像角点检测
            CvInvoke.Normalize(gray_scr, gray_scr, 0, 255, NormType.MinMax);//进行映射到【0，255】区域中。
            gray_scr = gray_scr.ToImage<Gray, byte>().Mat;

            /*提取角点坐标信息，在检测角点前提下*/
            //CvInvoke.AdaptiveThreshold(gray_scr, gray_scr, 255, AdaptiveThresholdType.GaussianC, ThresholdType.Binary, 9, -15); //这边采用局部阈值操作，避免全局阈值的阈值选择带来麻烦。推荐选择局部阈值方法。
            CvInvoke.Threshold(gray_scr, gray_scr, thread_valueref, 255, ThresholdType.Binary);// 阈值的设定的好坏直接决定角点提取的效果。
            VectorOfPoint points = new VectorOfPoint();//创建一个VectorOfPoint 类型，用于存储非0 像素的点。
            CvInvoke.FindNonZero(gray_scr, points);//找到非0 像素的位置。

            Point[] pt = points.ToArray();
            info_message = "Corners_Count:" + pt.Length.ToString() + " || ";
            for (int mm = 0; mm < pt.Length; mm++)
            {
                info_message += "Corner_" + (mm + 1).ToString() + ":Position:" + pt[mm].X + "," + pt[mm].Y + " || ";
            }

            return gray_scr.Clone();
        }

        /// <summary>
        /// 查找多邊形(幾何逼近)
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="contours"></param>
        /// <param name="value"></param>
        /// <returns></returns>
        public static Mat ApproxPolyDP_Func(Mat inputMat, VectorOfVectorOfPoint contours, int value)
        {
            Mat src = inputMat.Clone();
            Mat mask = src.ToImage<Bgr, byte>().CopyBlank().Mat;
            // Mat mask = m_CurrentMat.Clone();
            int ksize = contours.Size;//获取连通区域的个数。
            if (ksize == 0)
            {
                return null;
            }
            for (int i = 0; i < ksize; i++)//遍历每个连通轮廓。
            {
                VectorOfPoint contour = contours[i];//获取独立的连通轮廓
                VectorOfPoint approx_Curve = new VectorOfPoint();
                CvInvoke.ApproxPolyDP(contour, approx_Curve, CvInvoke.ArcLength(contour, false) * 0.05, true);//经常几何逼近，精度为连通域轮廓周长的0.05 倍。
                Point p1 = approx_Curve.ToArray()[0];//获得第一个点坐标。
                Point p2;//创建第二个点左边
                int j = 1;
                if (approx_Curve.Size == value)
                {
                    for (; j < approx_Curve.Size; j++)//遍历所有的点
                    {
                        p2 = approx_Curve.ToArray()[j];//获取第二个点95
                        CvInvoke.Line(mask, p1, p2, new MCvScalar(0, 0, 255), 2);//绘画直线
                        p1 = p2; //将第二个点左边赋值给第一个点
                    }
                }
                CvInvoke.Line(mask, approx_Curve.ToArray()[approx_Curve.Size - 1], approx_Curve.ToArray()[0], new MCvScalar(0, 0, 255), 3);//绘画最后一个闭合线段
            }
            src.Dispose();
            return mask.Clone();
        }

        /// <summary>
        /// 計算二值畫圖片黑白像素點數量 (經試驗此方法計算速度較慢)
        /// </summary>
        /// <param name="oldbitmap">輸入圖像</param>
        /// <returns>白黑像素點數量123,321</returns>
        public static string black_white_pixel_count(Bitmap oldbitmap)
        {
            //Bitmap oldbitmap = oldbitmap_1.Clone() as Bitmap;
            int Height = oldbitmap.Height;
            int Width = oldbitmap.Width;
            // Bitmap newbitmap = new Bitmap(Width, Height);
            Color pixel;
            int white_pixel = 0;
            int black_pixel = 0;
            for (int x = 0; x < Width - 1; x++)
            {
                for (int y = 0; y < Height - 1; y++)
                {
                    //int r, g, b;
                    pixel = oldbitmap.GetPixel(x, y);


                    if (pixel.R == 255 && pixel.G == 255 && pixel.B == 255)
                    {
                        white_pixel++;
                    }
                    else
                    {
                        black_pixel++;
                    }
                }
            }
            //oldbitmap.Dispose();
            return "White_Pixel_Count:" + white_pixel.ToString() + ",Black_Pixel_Count:" + black_pixel.ToString();
        }

        /// <summary>
        ///  計算二值畫圖片黑白像素點數量 (推薦使用,計算速度較快)
        /// </summary>
        /// <param name="bitmap"></param>
        /// <returns></returns>
        public static unsafe string Black_White_Pixel_Count(Bitmap bitmap)
        {
            Bitmap src = bitmap.Clone() as Bitmap;
            if (src == null)
            {
                throw new ArgumentNullException("bitmap");
            }

            int width = src.Width;
            int height = src.Height;
            Rectangle rect = new Rectangle(0, 0, width, height);
            int white_pixel = 0;
            int black_pixel = 0;
            try
            {
                BitmapData bitmapData = src.LockBits(
                    rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                byte* scan0 = (byte*)bitmapData.Scan0;
                int strideOffset = bitmapData.Stride - bitmapData.Width * 4;

                int sum = width * height;

                int a = 0;
                int r = 0;
                int g = 0;
                int b = 0;

                for (int i = 0; i < height; i++)
                {
                    for (int j = 0; j < width; j++)
                    {
                        b = *scan0++;
                        g = *scan0++;
                        r = *scan0++;
                        a = *scan0++;
                        if (r == 255 && g == 255 && b == 255)
                        {
                            white_pixel++;
                        }
                        else
                        {
                            black_pixel++;
                        }

                    }
                    scan0 += strideOffset;
                }

                src.UnlockBits(bitmapData);

                //a /= sum;
                //r /= sum;
                //g /= sum;
                //b /= sum;
                src.Dispose();
                return "White_Pixel_Count:" + white_pixel.ToString() + ",Black_Pixel_Count:" + black_pixel.ToString();
            }
            catch
            {
                return "White_Pixel_Count:-1" + ",Black_Pixel_Count:-1";
            }
        }

        /// <summary>
        /// 繪製1.外接矩形/2.最小面積矩形/3.外接圓/4.外接三角形/5.凸包
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="contours"></param>
        /// <param name="bmpCorp_Pic">是否進行摳圖</param>
        /// <param name="_scr_image">被摳圖的原圖</param>
        /// <param name="type">外接類型1~5</param>
        /// <param name="info_message"></param>
        /// <returns></returns>
        public static Mat External_Graphics(Mat inputMat, VectorOfVectorOfPoint contours, int type, int bmpCorp_Pic, Bitmap _scr_image, ref string info_message)
        {
            if (contours.Size == 0)
            {
                info_message = "Please extract the connected domain before performing this operation ";
                return null;
            }

            if (bmpCorp_Pic == 1)
            {
                #region Delete Pic
                try
                {
                    if (Directory.Exists(Application.StartupPath + "\\BmpCorp"))
                    {
                        string[] files = Directory.GetFiles(Application.StartupPath + "\\BmpCorp");
                        foreach (string file in files)
                        {
                            File.Delete(file);
                        }
                    }
                    else
                    {
                        Directory.CreateDirectory(Application.StartupPath + "\\BmpCorp");
                    }
                }
                catch (Exception ex)
                {

                }
                #endregion
            }
            Mat src = inputMat.Clone();
            Image<Bgr, byte> dst = src.ToImage<Bgr, byte>();// new Image<Bgr, byte>(m_CurrentMat.Size);//
            info_message = "Contours_Count:" + contours.Size.ToString() + " || ";
            for (int i = 0; i < contours.Size; i++)
            {
                info_message += "Contour_" + i.ToString() + ":";
                VectorOfPoint contour = contours[i];

                if (type == 0)
                {
                    Rectangle rect = CvInvoke.BoundingRectangle(contour);//提取最外部矩形。

                    #region 裁剪原圖
                    if (bmpCorp_Pic == 1)
                    {
                        Bitmap newBit = BitmapCut(_scr_image.Clone() as Bitmap, rect);

                        newBit.Save(Application.StartupPath + "\\BmpCorp" + "\\Rect" + (i + 1).ToString() + ".png");
                        newBit.Dispose();
                    }
                    #endregion

                    dst.Draw(rect, new Bgr(0, 255, 0), 1);//

                    info_message += "External_Rectangle_" + (i + 1).ToString() + ": X:" + rect.X + " Y:" + rect.Y + " Width:" + rect.Width + " Height:" + rect.Height + " || ";
                }
                else if (type == 1)
                {
                    RotatedRect rotaterect = CvInvoke.MinAreaRect(contour);//提取最小面积矩形。

                    #region 裁剪原圖
                    if (bmpCorp_Pic == 1)
                    {
                        PointF[] pt_f = rotaterect.GetVertices();
                        //pt_f.
                        Point[] pt = new Point[pt_f.Length];

                        for (int m = 0; m < pt_f.Length; m++)
                        {
                            pt[m] = Point.Truncate(pt_f[m]);
                        }

                        GraphicsPath path = new GraphicsPath();

                        path.AddLines(pt);

                        Bitmap newBit = null;

                        BitmapCrop(_scr_image.Clone() as Bitmap, path, out newBit);

                        newBit.Save(Application.StartupPath + "\\BmpCorp" + "\\Rotaterect" + (i + 1).ToString() + ".png");
                        newBit.Dispose();
                    }
                    #endregion

                    info_message += "Min_Area_External_Rectangle_" + (i + 1).ToString() + ": Angle:" + rotaterect.Angle + ": Center:" + rotaterect.Center.X + "," + rotaterect.Center.Y + " || ";
                    dst.Draw(rotaterect, new Bgr(255, 0, 0), 1);//
                }
                else if (type == 2)
                {
                    CircleF circlef = CvInvoke.MinEnclosingCircle(contour);//提取最小面积圆。
                    info_message += "Min_Area_Circle_" + (i + 1).ToString() + ": Area:" + circlef.Area + ": Center:" + circlef.Center.X + "," + circlef.Center.Y + " Radius:" + circlef.Radius + " || ";
                    dst.Draw(circlef, new Bgr(0, 0, 255), 1);//
                }
                else if (type == 3)
                {
                    VectorOfPoint tri = new VectorOfPoint();// 创建VectorOfPoint 类型，存储三角形。
                    double area = CvInvoke.MinEnclosingTriangle(contour, tri);//获取外接三角形。
                    Point[] pt = tri.ToArray();

                    #region 裁剪原圖
                    if (bmpCorp_Pic == 1)
                    {
                        GraphicsPath path = new GraphicsPath();

                        path.AddLines(pt);

                        Bitmap newBit = null;

                        BitmapCrop(_scr_image.Clone() as Bitmap, path, out newBit);

                        newBit.Save(Application.StartupPath + "\\BmpCorp" + "\\Tri" + (i + 1).ToString() + ".png");
                        newBit.Dispose();
                    }
                    #endregion

                    info_message += "External_Triangle_" + (i + 1).ToString() + ":Area:" + area + ":Point_1_Position:" + pt[0].X + "," + pt[0].Y + ":Point_2_Position:" + pt[1].X + "," + pt[1].Y + ":Point_3_Position:" + pt[2].X + "," + pt[2].Y + " || ";
                    dst.Draw(tri.ToArray(), new Bgr(0, 255, 255), 1);//
                }
                else if (type == 4)
                {
                    VectorOfPoint hull = new VectorOfPoint();//创建VectorOfPoint 存储凸包点

                    CvInvoke.ConvexHull(contour, hull);//凸包检测。

                    Point[] pt = hull.ToArray();

                    #region 裁剪原圖
                    if (bmpCorp_Pic == 1)
                    {
                        GraphicsPath path = new GraphicsPath();

                        path.AddLines(pt);

                        Bitmap newBit = null;

                        BitmapCrop(_scr_image.Clone() as Bitmap, path, out newBit);

                        newBit.Save(Application.StartupPath + "\\BmpCorp" + "\\Hull" + (i + 1).ToString() + ".png");
                        newBit.Dispose();
                    }
                    #endregion

                    for (int mm = 0; mm < pt.Length; mm++)
                    {
                        info_message += "Convex_Hull_Point_" + (i + 1).ToString() + ":Position:" + pt[mm].X + "," + pt[mm].Y + " || ";
                    }

                    dst.Draw(hull.ToArray(), new Bgr(255, 0, 255), 1);//
                }
            }
            src.Dispose();
            return Bmp2Mat(dst.Bitmap.Clone() as Bitmap);
        }

        /// <summary>
        /// 查找連通域中的圓(根據半徑篩選)
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="contours">圖像中的連通域</param>
        /// <param name="min_R">最小半徑</param>
        /// <param name="max_R">最大半徑</param>
        /// <param name="info_message"></param>
        /// <returns></returns>
        public static Mat Find_Circle(Mat inputMat, VectorOfVectorOfPoint contours, int min_R, int max_R, ref string info_message)
        {
            if (contours.Size == 0)
            {
                info_message = "Please extract the connected domain before performing this operation ";
                return null;
            }
            VectorOfVectorOfPoint cricle_vvp = new VectorOfVectorOfPoint();//存储筛选过后圆的轮廓.
            CircleF circle = new CircleF();
            int ksize = contours.Size;//获取连通区域的个数。
            Mat src1 = inputMat.Clone();
            Image<Bgr, byte> src = src1.ToImage<Bgr, byte>();
            int circle_num = 0;
            for (int i = 0; i < ksize; i++)//遍历所有轮廓
            {
                double area = CvInvoke.ContourArea(contours[i]);//假设如果轮廓为圆，即面积为:PI*R^2
                double length = CvInvoke.ArcLength(contours[i], true);//假设如果轮廓为圆，即周长为:PI*R*2
                double r = (area / length) * 2;//假设如果轮廓为圆: 面积/周长=R/2；即半径为： 面积*2/周长
                double c = (area / (length * length));//假设轮廓为圆： 面积/(周长的平方)=1/(4*PI)常数； 0.0796                 
                if (c > 0.063 && c < 0.08)//满足相应条件
                {
                    if (r < max_R && r > min_R)
                    {
                        cricle_vvp.Push(contours[i]);//提取筛选后的圆轮廓
                        circle = CvInvoke.MinEnclosingCircle(contours[i]);
                        circle_num++;
                        info_message += "Circle_" + circle_num + ":Proportional_Value:" + c + ":Radius:" + r + " || " + " Circle_Center:" + circle.Center.X + "," + circle.Center.Y + " || ";
                    }
                }
            }

            if (cricle_vvp.Size == 0)
            {
                info_message = "Not find circle！";
                return null;
            }
            else
            {
                for (int i = 0; i < cricle_vvp.Size; i++)
                {
                    //顯示最小外接矩形
                    //Rectangle rect = CvInvoke.BoundingRectangle(cricle_vvp[i]);
                    //src.Draw(rect, new Bgr(0, 0, 255), 1);

                    //顯示最小面積圓
                    circle = CvInvoke.MinEnclosingCircle(cricle_vvp[i]);
                    CvInvoke.Circle(src, new Point((int)circle.Center.X, (int)circle.Center.Y), (int)circle.Radius, new Bgr(0, 0, 255).MCvScalar, 1);
                }
                src1.Dispose();
                return src.Mat.Clone();
            }
        }

        /// <summary>
        /// 查找線段
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="rho">距离分辨率</param>
        /// <param name="HoughLinesThershold">交点个数阈值</param>
        /// <param name="minLineLenth">最小直线长度</param>
        /// <param name="maxGrap">最大直线間间隙</param>
        /// <param name="info_message"></param>
        /// <returns></returns>
        public static Mat Find_Line(Mat inputMat, double rho, int HoughLinesThershold, double minLineLenth, double maxGrap, ref string info_message)
        {

            Mat threshold_scr = inputMat.Clone();

            Image<Bgr, byte> img = new Image<Bgr, byte>(threshold_scr.Width, threshold_scr.Height, new Bgr(255, 255, 255));

            LineSegment2D[] lines = CvInvoke.HoughLinesP(threshold_scr,//8位单通道图像
                                            rho, //距离分辨率
                                            Math.PI / 180, //角度分辨率
                                            HoughLinesThershold,//交点个数阈值
                                            minLineLenth,//最小直线长度
                                            maxGrap//最大直线间隙,间隙大于该值，则被认为是两条线段，否则是一条
                                            );
            info_message = "Find_Lines:" + lines.Length + ":";
            Image<Bgr, byte> src2 = img.Copy();
            for (int i = 0; i < lines.Length; ++i)
            {
                CvInvoke.Line(src2, lines[i].P1, lines[i].P2, new Bgr(0, 0, 255).MCvScalar, 1);//在原图像中画线
                //double angle = lines[i].Direction; //Math.Atan2(lines[i].P1.Y - lines[i].P2.Y, lines[i].P1.X - lines[i].P2.X);
                double angle = 0;
                if (lines[i].P1.X == lines[i].P2.X)
                {
                    angle = 90;
                }
                else if (lines[i].P1.Y == lines[i].P2.Y)
                {
                    angle = 0;
                }
                else
                {
                    Point Start = new Point(Math.Abs((lines[i].P1.X - lines[i].P2.X) / 2 - 100), Math.Abs((lines[i].P1.Y - lines[i].P2.Y) / 2));
                    Point End = new Point(Math.Abs((lines[i].P1.X - lines[i].P2.X) / 2 + 100), (Math.Abs((lines[i].P1.Y - lines[i].P2.Y) / 2)));
                    LineSegment2D line_NEW = new LineSegment2D(Start, End);
                    angle = lines[i].GetExteriorAngleDegree(line_NEW);
                }

                double length = lines[i].Length;

                info_message += ("Line_" + (i + 1) + " Length:" + length + " Angle:" + angle + " || ").ToString();
            }
            threshold_scr.Dispose();
            return src2.Mat.Clone();
        }

        /// <summary>
        /// 图像缩放
        /// </summary>
        /// <param name="InputMat">輸入圖像</param>
        /// <param name="num_X">X軸縮放比例</param>
        /// <param name="num_Y">Y軸縮放比例</param>
        /// <returns></returns>
        public static Mat ImageResize(Mat InputMat, double num_X, double num_Y)
        {
            Mat dst = new Mat();
            Mat src = InputMat.Clone();
            CvInvoke.Resize(src, dst, new Size(0, 0), num_X, num_Y, Emgu.CV.CvEnum.Inter.Cubic);
            src.Dispose();
            return dst;
        }

        /// <summary>
        /// 仿射變換
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="Scale">仿射倍數</param>
        /// <param name="Angle_Change">仿射角度</param>
        /// <returns></returns>
        public static Mat WarpAffineFun(Mat inputMat, double Scale, double Angle_Change)
        {
            Mat src = inputMat.Clone();
            int width = src.Cols;
            int height = src.Rows;
            Mat mapMatrix = new Mat();
            Mat dst = new Mat();
            // CvInvoke.GetRotationMatrix2D(Center, (double)Angle, 1.0, mapMatrix);
            CvInvoke.GetRotationMatrix2D(new PointF(width / 2, height / 2), Angle_Change, Scale, dst);
            //CvInvoke.WarpAffine(src, src, mapMatrix, src.Size, Inter.Linear, Warp.Default, BorderType.Constant, new MCvScalar());
            Mat dst_Mat = new Mat();
            CvInvoke.WarpAffine(src, dst_Mat, dst, src.Size);
            src.Dispose();
            return dst_Mat;
        }

        /// <summary>
        /// 圖像旋轉
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <param name="Angle">旋轉角度</param>
        /// <returns></returns>
        public static Mat Rotate_Image(Mat inputMat, double Angle)
        {
            Mat OperationMat = inputMat.Clone();
            Image<Gray, byte> img = OperationMat.ToImage<Gray, byte>();
            img = img.Rotate(Angle, new Gray(), false);
            OperationMat.Dispose();
            return img.Mat;
        }

        /// <summary>
        /// 透視翻轉
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <returns></returns>
        public static Mat WarpPerspective_Func(Mat inputMat)
        {
            Mat dst_mat = new Mat();
            Mat scr_mat = inputMat.Clone();
            PointF[] scr = new PointF[] { new PointF(0, 0), new PointF(scr_mat.Width, 0), new PointF(0, scr_mat.Height), new PointF(scr_mat.Width, scr_mat.Height) };
            PointF[] dst = new PointF[] { new PointF(scr_mat.Width, scr_mat.Height), new PointF(0, scr_mat.Height), new PointF(scr_mat.Width, 0), new PointF(0, 0) };
            Mat data = CvInvoke.GetPerspectiveTransform(scr, dst);
            CvInvoke.WarpPerspective(scr_mat, dst_mat, data, scr_mat.Size);
            return dst_mat.Clone();
        }

        /// <summary>
        /// 反色
        /// </summary>
        /// <param name="inputMat">輸入圖像</param>
        /// <returns></returns>
        public static Mat BitwiseNot_Function(Mat inputMat)
        {
            if (inputMat.NumberOfChannels != 1)
            {
                throw new Exception("不是单通道图像");
            }
            Mat src = inputMat.Clone();
            Mat dst = new Mat();
            CvInvoke.BitwiseNot(src, dst, null);
            src.Dispose();
            return dst.Clone();
        }

        /// <summary>
        /// 锐化
        /// </summary>
        /// <param name="inputMat">输入图像</param>
        /// <param name="kernelValue">核</param>
        /// <returns></returns>
        public static Mat Shape(Mat inputMat, int kernelValue)
        {
            Mat inputMat_1 = inputMat;
            float[, ,] kernel = { { { 0 }, { -1 }, { 0 } }, { { -1 }, { kernelValue }, { -1 } }, { { 0 }, { -1 }, { 0 } } };
            Image<Gray, float> kernelImg = new Image<Gray, float>(kernel);
            Mat result = new Mat(inputMat_1.Size, inputMat_1.Depth, inputMat_1.NumberOfChannels);
            CvInvoke.Filter2D(inputMat_1, result, kernelImg, new Point(-1, -1));
            inputMat_1.Dispose();
            return result;
        }

        /// <summary>
        /// 漫水填充
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="seekPoint"></param>
        public static int FloodFill(Mat inputMat, Point seekPoint)
        {
            Rectangle rect = new Rectangle();
            Mat src = inputMat.Clone();
            int num = CvInvoke.FloodFill(src, null, seekPoint, new MCvScalar(255, 255, 255), out rect, new MCvScalar(1, 1, 1), new MCvScalar(1, 1, 1));
            src.Dispose();
            return num;
        }

        /// <summary>
        /// 图片截图
        /// </summary>
        /// <param name="bitmap">原图</param>
        /// <param name="path">裁剪路径</param>
        /// <param name="outputBitmap">输出图</param>
        /// <returns></returns>
        public static void BitmapCrop(Bitmap bitmap, GraphicsPath path, out Bitmap outputBitmap)
        {
            RectangleF rect = path.GetBounds();
            int left = (int)rect.Left;
            int top = (int)rect.Top;
            int width = (int)rect.Width;
            int height = (int)rect.Height;
            Bitmap image = (Bitmap)bitmap.Clone();
            outputBitmap = new Bitmap(width, height);
            for (int i = left; i < left + width; i++)
            {
                for (int j = top; j < top + height; j++)
                {
                    //判断坐标是否在路径中   
                    if (path.IsVisible(i, j))
                    {
                        //复制原图区域的像素到输出图片   
                        outputBitmap.SetPixel(i - left, j - top, image.GetPixel(i, j));
                        //设置原图这部分区域为透明   
                        image.SetPixel(i, j, Color.FromArgb(0, image.GetPixel(i, j)));
                    }
                    else
                    {
                        outputBitmap.SetPixel(i - left, j - top, Color.FromArgb(0, 255, 255, 255));
                    }
                }
            }
            image.Dispose();
            bitmap.Dispose();
            //return outputBitmap;
        }

        /// <summary>
        /// OCR檢測
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="OCR 信息"></param>
        /// <returns></returns>
        public static Mat OCR(Mat inputMat, ref string info_message)
        {
            info_message = OcrFun_Lib.OcrStr(inputMat.Clone());

            return inputMat.Clone();
        }

        /// <summary>
        /// Color解析
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="Color 信息(顏色,H,S,L,R,G,B)"></param>
        /// <returns></returns>
        public static Mat Color_Anylaze(Mat inputMat, ref string info_message)
        {
            info_message = Color_Analyze.Get_Color_info(inputMat.Clone().Bitmap);
            return inputMat.Clone();
        }

        /// <summary>
        /// 條形碼識別
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="info_message"></param>
        /// <returns></returns>
        public static Mat BarCode_Anylaze(Mat inputMat, ref string info_message)
        {
            BarCode.Reader rd = new BarCode.Reader();
            string barCode = "";
            float angle = 0;
            RotatedRect RecRes = new RotatedRect();
            barCode = rd.ReadCode128((inputMat.Clone()), out RecRes);
            angle = RecRes.Angle;
            info_message = barCode + "," + angle.ToString();
            return inputMat.Clone();
        }

        /// <summary>
        /// 二維碼識別
        /// </summary>
        /// <param name="inputMat"></param>
        /// <param name="info_message"></param>
        /// <returns></returns>
        public static Mat QRCode_Anylaze(Mat inputMat, ref string info_message)
        {
            BarCode.Reader rd = new BarCode.Reader();
            string QR_Code = "";
            float angle = 0;
            RotatedRect RecRes = new RotatedRect();
            QR_Code = rd.ReadECC200(inputMat.Clone(), out RecRes).Trim();
            if (QR_Code == "")
            {
                QR_Code = rd.ReadQR(inputMat.Clone(), out RecRes);
            }
            angle = RecRes.Angle;
            info_message = QR_Code + "," + angle.ToString();
            return inputMat.Clone();
        }
    }
}
