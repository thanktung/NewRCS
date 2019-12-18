namespace Histogram_Lib
{
    using Emgu.CV;
    using System;
    using System.Drawing;

    public static class Histogram
    {
        public static Bitmap DrawHist(int[] data, int width, int height)
        {
            Bitmap image = new Bitmap(width, height);
            double num2 = ((double) GetMax(data)) / ((double) height);
            using (Graphics graphics = Graphics.FromImage(image))
            {
                for (int i = 0; i < data.Length; i++)
                {
                    int x = (int) ((i * width) / ((double) data.Length));
                    int num5 = (int) (((double) data[i]) / num2);
                    graphics.DrawLine(Pens.Black, new Point(x, height), new Point(x, height - num5));
                }
            }
            return image;
        }

        public static int[] GetData(Mat inputMat)
        {
            int[] numArray = new int[0x100];
            for (int i = 0; i < inputMat.Rows; i++)
            {
                for (int j = 0; j < inputMat.Cols; j++)
                {
                    int index = inputMat.GetData(new int[] { i, j })[0];
                    numArray[index]++;
                }
            }
            return numArray;
        }

        public static int[] GetData(Mat inputMat, Mat mask)
        {
            int[] numArray = new int[0x100];
            for (int i = 0; i < inputMat.Rows; i++)
            {
                for (int j = 0; j < inputMat.Cols; j++)
                {
                    int num3 = mask.GetData(new int[] { i, j })[0];
                    if (num3 > 0)
                    {
                        int index = inputMat.GetData(new int[] { i, j })[0];
                        numArray[index]++;
                    }
                }
            }
            return numArray;
        }

        public static int GetMax(int[] data)
        {
            int num = -2147483648;
            for (int i = 0; i < data.Length; i++)
            {
                if (num < data[i])
                {
                    num = data[i];
                }
            }
            return num;
        }

        public static int GetMaxIndex(int[] data)
        {
            int num = -2147483648;
            int num2 = -1;
            for (int i = 0; i < data.Length; i++)
            {
                if (num < data[i])
                {
                    num = data[i];
                    num2 = i;
                }
            }
            return num2;
        }
    }
}

