using Emgu.CV;
using EmgucvLib;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text;

namespace DVision
{
    public class Hist
    {
        public static Bitmap DrawGrayHist(Mat inputMat)
        {
            Mat OperationMat = inputMat.Clone();
            int[] data = Histogram.GetData(OperationMat);
            int Max = Histogram.GetMax(data);
            return DrawHist(data, Max);
        }

        public static Bitmap DrawAreaHist(List<Connection> cntList, int MaxArea)
        {
            int[] data = GetData(cntList, MaxArea);
            int Max = Histogram.GetMax(data);
            return DrawHist(data, Max);
        }

        private static int[] GetData(List<Connection> cntList, int MaxArea)
        {
            double XScale = MaxArea / 255.0;
            int[] data = new int[256];
            for (int num = 0; num < cntList.Count; num++)
            {
                int value = (int)(cntList[num].Area / XScale);
                data[value]++;
            }
            return data;
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
    }

}
