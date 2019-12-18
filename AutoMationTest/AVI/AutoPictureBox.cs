using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Data;
using System.Text;
using System.Windows.Forms;
using Emgu.CV.Structure;
using Emgu.CV;
using System.Drawing.Drawing2D;

namespace SurfDetection
{
    public partial class AutoPictureBox : UserControl
    {
        private Bitmap m_InputBmp = null;
        private Size m_ImgOriginalSize, m_PbOriginalSize;   //图像原始尺寸，画板原始尺寸
        private Point m_ImgStartPoint, m_PbStartPoint;      //图像起始点，画板起始点
        public Point m_ImgPoint, m_PbPoint,m_MarkPoint;                //图像点，画板点
        private Rectangle m_ImgRect, m_PbRect;              //图像矩形框，画板矩形框
        private bool m_IsInitialImg = false;                //画板前是否已初始化图像
        private bool m_IsMouseDown = false;                 //鼠标是否已按下
        private bool m_IsMouseMove = false;                 //鼠标是否移动
        private Image<Bgr, byte> img = null;
        public string Image_Path = "";
        public enum MouseMode
        {
            NONE = 0,
            SELECTION = 1,    //框选
            DRAG = 2,         //拖动
        }
        private MouseMode m_MouseMode;

        /// <summary>
        /// 设置当前画板的右键菜单是否可用
        /// </summary>
        /// <param name="isUse"></param>
        public void SetRightMenu(bool isUse)
        {
            pb_ImgShow.ContextMenuStrip = isUse ? contextMenuStrip : null;
        }

        /// <summary>
        /// 图像矩形框
        /// </summary>
        public Rectangle ImgRectangle
        {
            get { return this.m_ImgRect; }
            private set { this.m_ImgRect = value; }
        }

        /// <summary>
        /// 画板矩形框
        /// </summary>
        public Rectangle PbRectangle
        {
            get { return this.m_PbRect; }
            private set { this.m_PbRect = value; }
        }

        /// <summary>
        /// 画板背景图像
        /// </summary>
        public Image BackgroundImg
        {
            get { return this.pb_ImgShow.BackgroundImage; }
            set { pb_ImgShow.BackgroundImage = value; }
        }

        /// <summary>
        /// 画板前景图
        /// </summary>
        public Image ForegroundImg
        {
            get { return this.pb_ImgShow.Image; }
            set { pb_ImgShow.Image = value; }
        }

        public AutoPictureBox()
        {
            InitializeComponent();

            this.DoubleBuffered = true;
        }

        private void AutoPictureBox_Load(object sender, EventArgs e)
        {
            pb_ImgShow.Image = null;
            pb_ImgShow.BackgroundImage = null;
           // pb_ImgShow.MouseWheel += new MouseEventHandler(pb_ImShow_MouseWheel);
        }

        private void AutoPictureBox_SizeChanged(object sender, EventArgs e)
        {
            //获取画板尺寸
            m_PbOriginalSize = pb_ImgShow.Size;
            this.pb_ImgShow.Size = this.Size;
        }

        #region PictureBox MouseEvent

        private void pb_ImShow_MouseDown(object sender, MouseEventArgs e)
        {
            if (m_InputBmp == null)
                return;

            if (e.Button == System.Windows.Forms.MouseButtons.Left)
            {
                lock (m_InputBmp)
                {
                    //计算图像/画板起始点
                    CalcPoint(e.Location);
                    //保存起始点
                    m_PbStartPoint = m_PbPoint;
                    m_ImgStartPoint = m_ImgPoint;

                    m_IsMouseDown = true;
                    m_IsMouseMove = false;
                }
            }
        }

        private void pb_ImShow_MouseMove(object sender, MouseEventArgs e)
        {
            //当画板上没有图像时，返回
            if (m_InputBmp == null)
                return;

            //鼠标移动到画板上时获取焦点
            if (!pb_ImgShow.Focused)
                pb_ImgShow.Focus();

            //实时刷新当前坐标
            CalcPoint(e.Location);

            tslbl_ScaleMousePos.Text = "画板坐标：" + m_PbPoint.X.ToString() + ", " + m_PbPoint.Y.ToString();
            tslbl_RealMousePos.Text = "实际坐标：" + m_ImgPoint.X.ToString() + ", " + m_ImgPoint.Y.ToString();

            if (m_IsMouseDown)
            {
                lock (m_InputBmp)
                {
                    switch (m_MouseMode)
                    {
                        case MouseMode.DRAG:
                            DragImage(m_PbPoint);
                            break;
                        case MouseMode.SELECTION:
                            using (Graphics g = pb_ImgShow.CreateGraphics())
                            {
                                pb_ImgShow.Refresh();
                                //g.SmoothingMode = SmoothingMode.AntiAlias;
                                g.PixelOffsetMode = PixelOffsetMode.Half;
                                g.DrawRectangle(Pens.Blue,
                                                new Rectangle(Math.Min(m_PbPoint.X, m_PbStartPoint.X), Math.Min(m_PbPoint.Y, m_PbStartPoint.Y),
                                                              Math.Abs(m_PbPoint.X - m_PbStartPoint.X), Math.Abs(m_PbPoint.Y - m_PbStartPoint.Y)));
                            }
                            break;
                        default:
                            break;
                    }
                }
            }

            m_IsMouseMove = true;
        }

        private void pb_ImShow_MouseUp(object sender, MouseEventArgs e)
        {
            if (m_IsMouseMove)
            {
                if (m_MouseMode == MouseMode.SELECTION)
                {
                    CalcPoint(e.Location);
                    m_PbRect = new Rectangle(Math.Min(m_PbPoint.X, m_PbStartPoint.X), Math.Min(m_PbPoint.Y, m_PbStartPoint.Y),
                                             Math.Abs(m_PbPoint.X - m_PbStartPoint.X), Math.Abs(m_PbPoint.Y - m_PbStartPoint.Y));

                    m_ImgRect = new Rectangle(Math.Min(m_ImgPoint.X, m_ImgStartPoint.X), Math.Min(m_ImgPoint.Y, m_ImgStartPoint.Y),
                                              Math.Abs(m_ImgPoint.X - m_ImgStartPoint.X), Math.Abs(m_ImgPoint.Y - m_ImgStartPoint.Y));
                }

                m_MouseMode = MouseMode.NONE;
                pb_ImgShow.Cursor = Cursors.Default;
            }

            m_IsMouseDown = false;
        }

        private void pb_ImShow_MouseWheel(object sender, MouseEventArgs e)
        {
            //当画板上没有图像时，返回
            if (pb_ImgShow.BackgroundImage == null)
                return;

            lock (m_InputBmp)
            {
                if (e.Delta > 0)
                {
                    //放大成图像原始大小
                    if (pb_ImgShow.Width != m_ImgOriginalSize.Width)
                    {
                        pb_ImgShow.Size = m_ImgOriginalSize;
                        int deltX = m_PbPoint.X - m_ImgPoint.X + pb_ImgShow.Location.X;
                        int deltY = m_PbPoint.Y - m_ImgPoint.Y + pb_ImgShow.Location.Y;
                        pb_ImgShow.Location = new Point(deltX, deltY);
                    }
                }
                else
                {
                    //缩小成画板原始大小
                    if (pb_ImgShow.Width != m_PbOriginalSize.Width)
                    {
                        pb_ImgShow.Size = m_PbOriginalSize;
                        pb_ImgShow.Location = new Point(0, 0);
                    }
                }
            }
        }

        #endregion

        #region PictureBox Right_Click Menu
        //打开图片
        private void ToolStripMenuItem_OpenImg_Click(object sender, EventArgs e)
        {
            OpenFileDialog ofd = new OpenFileDialog();
            ofd.Filter = "(*.jpg,*.png,*.jpeg,*.bmp,*.gif)|*.jpg;*.png;*.jpeg;*.bmp;*.gif|All files(*.*)|*.*";
            if (ofd.ShowDialog() == System.Windows.Forms.DialogResult.OK)
            {
                Bitmap bmp = new Bitmap(ofd.FileName);
                LoadImage(bmp);
                //pb_ImgShow.BackgroundImage = bmp; Bing 嘗試取消
                Image_Path = ofd.FileName;
                //还原图像显示
                ToolStripMenuItem_RestoreImg_Click(null, null);
            }

        }

        //框选图片
        private void ToolStripMenuItem_Selection_Click(object sender, EventArgs e)
        {
            if (pb_ImgShow.BackgroundImage == null)
                return;

            m_MouseMode = MouseMode.SELECTION;
            pb_ImgShow.Cursor = Cursors.Cross;
        }

        //拖拽图片
        private void ToolStripMenuItem_Drag_Click(object sender, EventArgs e)
        {
            if (pb_ImgShow.BackgroundImage == null)
                return;

            m_MouseMode = MouseMode.DRAG;
            pb_ImgShow.Cursor = Cursors.Hand;
        }

        //取消操作
        private void ToolStripMenuItem_Cancel_Click(object sender, EventArgs e)
        {
            m_MouseMode = MouseMode.NONE;
            pb_ImgShow.Cursor = Cursors.Default;
        }

        //还原图像
        public void ToolStripMenuItem_RestoreImg_Click(object sender, EventArgs e)
        {
            if (pb_ImgShow.BackgroundImage == null)
                return;
            pb_ImgShow.Size = m_PbOriginalSize;
            pb_ImgShow.Location = this.Location;
            pb_ImgShow.Refresh();

            m_MouseMode = MouseMode.NONE;
            pb_ImgShow.Cursor = Cursors.Default;
        }

        //清除图像
        private void ToolStripMenuItem_ClearImg_Click(object sender, EventArgs e)
        {
            pb_ImgShow.Image = null;
            pb_ImgShow.BackgroundImage = null;

            pb_ImgShow.Refresh();
        }

        //保存图片
        private void ToolStripMenuItem_SaveImg_Click(object sender, EventArgs e)
        {
            if (pb_ImgShow.BackgroundImage == null)
            {
                MessageBox.Show("保存图片失败.", "保存提示", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            SaveFileDialog sfd = new SaveFileDialog();
            //设置自动在文件名中添加扩展名
            sfd.AddExtension = true;
            //设置文件类型
            sfd.Filter = "BMP(*.bmp)|*.bmp|PNG(*.png)|*.png|JPEG(*.jpeg)|*.jpeg|JPG(*.jpg)|*.jpg|GIF(*.gif)|*.gif";
            //设置默认文件类型显示顺序
            sfd.FilterIndex = 1;
            //设置记忆上次打开的目录
            sfd.RestoreDirectory = true;

            if (sfd.ShowDialog() == DialogResult.OK)
            {
                //string sFilePath = sfd.FileName;
                //string sFileName = sFilePath.Substring(sFilePath.LastIndexOf("\\") + 1);

                pb_ImgShow.BackgroundImage.Save(sfd.FileName);
            }

        }

        #endregion

        #region Public Methods

        /// <summary>
        /// 刷新控件
        /// </summary>
        public void PbRefresh()
        {
            this.Invoke(new EventHandler(delegate
            {
                pb_ImgShow.Refresh();
            }));
        }

        /// <summary>
        /// 使PictureBox前景/背景图像无效
        /// </summary>
        public void PbImgDispose()
        {
            this.Invoke(new EventHandler(delegate
            {
                pb_ImgShow.Image = null;
                pb_ImgShow.BackgroundImage = null;
            }));
        }

        /// <summary>
        /// 加载图片
        /// </summary>
        /// <param name="bmp"></param>
        public void LoadImage(Bitmap bmp)
        {
            try
            {
                if (pb_ImgShow.Image != null)
                    pb_ImgShow.Image.Dispose();

                if (pb_ImgShow.BackgroundImage != null)
                    pb_ImgShow.BackgroundImage.Dispose();

                //if (!m_IsInitialImg)
                //{
                //获取图像的宽和高
                m_ImgOriginalSize = bmp.Size;
                //按照图像比例设定画板比例
                //AutoPbSize(bmp.Size);

                //    m_IsInitialImg = true;
                //}

                m_InputBmp = (Bitmap)bmp.Clone();
                pb_ImgShow.BackgroundImage = m_InputBmp;

                //if (pb_ImShow.Image == null)
                pb_ImgShow.Image = new Bitmap(m_ImgOriginalSize.Width, m_ImgOriginalSize.Height);
                pb_ImgShow.Refresh();
            }
            catch(Exception ex)
            {

            }
        }

        /// <summary>
        /// Bitmap转Mat
        /// </summary>
        /// <param name="bmpImage">Bitmap图像</param>
        /// <returns></returns>
        public Mat BmpToMat(Bitmap bmpImage)
        {
            Emgu.CV.Image<Bgr, Byte> currentFrame = new Emgu.CV.Image<Bgr, Byte>(bmpImage);
            Mat invert = new Mat();
            CvInvoke.BitwiseAnd(currentFrame, currentFrame, invert);
            return invert;
        }

        /// <summary>
        /// 攫取图像
        /// </summary>
        /// <param name="bmp">原始图像</param>
        /// <param name="nStartX">起始点X</param>
        /// <param name="nStartY">起始点Y</param>
        /// <param name="nWidth">宽度</param>
        /// <param name="nHeight">高度</param>
        /// <returns></returns>
        public Bitmap BitmapCut(Bitmap bmp, int nStartX, int nStartY, int nWidth, int nHeight)
        {
            if (bmp == null)
                return null;

            int w = bmp.Width;
            int h = bmp.Height;

            if (nStartX >= w || nStartY >= h)
                return null;

            if (nStartX + nWidth > w)
                nWidth = w - nStartX;
            if (nStartY + nHeight > h)
                nHeight = h - nStartY;

            try
            {
                Bitmap bmpOut = new Bitmap(nWidth, nHeight, System.Drawing.Imaging.PixelFormat.Undefined);
                Graphics g = Graphics.FromImage(bmpOut);
                g.DrawImage(bmp, new Rectangle(0, 0, nWidth, nHeight), new Rectangle(nStartX, nStartY, nWidth, nHeight), GraphicsUnit.Pixel);
                return bmpOut;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 攫取图像
        /// </summary>
        /// <param name="bmp">原始图像</param>
        /// <param name="rect">攫取范围</param>
        /// <returns></returns>
        public Bitmap BitmapCut(Bitmap bmp, Rectangle rect)
        {
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

                return bmpOut;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 攫取图像
        /// </summary>
        /// <param name="mat">原始图像</param>
        /// <param name="rec">攫取范围</param>
        /// <returns></returns>
        public Bitmap BitmapCut(Mat mat, Rectangle rec)
        {
            Bitmap img = new Bitmap(rec.Width, rec.Height);
            Bitmap source = mat.Bitmap;
            for (int i = 1; i < rec.Width; i++)
            {
                for (int j = 1; j < rec.Height; j++)
                {
                    img.SetPixel(i, j, source.GetPixel(rec.X + i - 1, rec.Y + j - 1));
                }
            }
            return img;
        }

        /// <summary>
        /// 画板表面绘制矩形
        /// </summary>
        /// <param name="pen">画笔</param>
        /// <param name="rect">矩形</param>
        public void DrawPbSurfaceRect(Pen pen, Rectangle rect)
        {
            lock (pb_ImgShow)
            {
                using (Graphics g = pb_ImgShow.CreateGraphics())
                {
                    g.DrawRectangle(pen, rect);
                }
            }
        }

        /// <summary>
        /// 图像上绘制矩形
        /// </summary>
        /// <param name="img">原始图片</param>
        /// <param name="pen">画笔</param>
        /// <param name="rect">矩形</param>
        /// <param name="angle">旋转角度</param>
        /// <param name="str">字符</param>
        /// <returns></returns>
        public Image DrawImageRect(Image img, Pen pen, Rectangle rect, float angle, string str)
        {
            try
            {
                PointF centerPoint = new PointF(rect.X + rect.Width / 2, rect.Y + rect.Height / 2);

                Matrix matrix = new Matrix();
                matrix.RotateAt(angle, centerPoint);

                this.Invoke(new EventHandler(delegate
                {
                    using (Graphics g = Graphics.FromImage(img))
                    {
                        if (str != "")
                            g.DrawString(str, new Font("宋体", 21), pen.Brush, centerPoint);

                        g.Transform = matrix;
                        g.DrawRectangle(pen, rect);
                    }
                }));

                return img;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 图像上绘制矩形
        /// </summary>
        /// <param name="pen">画笔</param>
        /// <param name="rect">矩形</param>
        /// <returns></returns>
        public void DrawImageRect(Pen pen, Rectangle rect)
        {
            try
            {
                this.Invoke(new EventHandler(delegate
                {
                    using (Graphics g = Graphics.FromImage(pb_ImgShow.Image))
                    {
                        g.DrawRectangle(pen, rect);
                    }
                }));

            }
            catch
            {
                //return null;
            }
        }

        /// <summary>
        /// 图像上绘制字符
        /// </summary>
        /// <param name="str">字符</param>
        /// <param name="pen">画笔</param>
        /// <param name="pos">绘制点</param>
        /// <returns></returns>
        public void DrawImageString(string str, Pen pen, Point pos)
        {
            try
            {
                this.Invoke(new EventHandler(delegate
                {
                    using (Graphics g = Graphics.FromImage(pb_ImgShow.Image))
                    {
                        g.DrawString(str, new Font("宋体", 21), pen.Brush, pos);
                    }
                }));
            }
            catch
            {

            }
        }

        /// <summary>
        /// 由画板中点计算图像中对应点
        /// </summary>
        /// <param name="p">画板中点</param>
        /// <returns>图像中点</returns>
        private Point CalcImgPoint(Point p)
        {
            return new Point((int)((double)m_ImgOriginalSize.Width / pb_ImgShow.Width * p.X),
                                    (int)((double)m_ImgOriginalSize.Height / pb_ImgShow.Height * p.Y));
        }

        /// <summary>
        /// 由图像中点计算画板中对应点
        /// </summary>
        /// <param name="p">图像中点</param>
        /// /// <returns>画板中点</returns>
        private Point CalcPbPoint(Point p)
        {
            return new Point((int)((double)pb_ImgShow.Width / m_ImgOriginalSize.Width * p.X),
                                  (int)((double)pb_ImgShow.Height / m_ImgOriginalSize.Height * p.Y));
        }

        /// <summary>
        /// 由画板中矩形计算图像中对应矩形
        /// </summary>
        /// <param name="rect">画板中矩形</param>
        /// <returns>图像中矩形</returns>
        public Rectangle CalcImgRectangle(Rectangle rect)
        {
            Point startPoint = CalcImgPoint(rect.Location);
            return new Rectangle(startPoint, new Size((int)((double)m_ImgOriginalSize.Width / pb_ImgShow.Width * rect.Width), (int)((double)m_ImgOriginalSize.Height / pb_ImgShow.Height * rect.Height)));
        }

        /// <summary>
        /// 由图像中矩形计算画板中对应矩形
        /// </summary>
        /// <param name="rect">图像中矩形</param>
        /// <returns>画板中矩形</returns>
        public Rectangle CalcPbRectangle(Rectangle rect)
        {
            Point startPoint = CalcPbPoint(rect.Location);
            return new Rectangle(startPoint, new Size((int)((double)pb_ImgShow.Width / m_ImgOriginalSize.Width * rect.Width), (int)((double)pb_ImgShow.Height / m_ImgOriginalSize.Height * rect.Height)));
        }

        #endregion

        #region Private Methods

        /// <summary>
        /// 根据图像 Width/Height 比例,调整 PictureBox Width & Height 
        /// </summary>
        /// <param name="bmpSize"></param>
        private void AutoPbSize(Size bmpSize)
        {
            double wScale = (double)pb_ImgShow.Width / bmpSize.Width;
            double hScale = (double)pb_ImgShow.Height / bmpSize.Height;

            if (wScale <= hScale)
            {
                pb_ImgShow.Height = (int)(pb_ImgShow.Width / ((double)bmpSize.Width / bmpSize.Height));
            }
            else
            {
                pb_ImgShow.Width = (int)(pb_ImgShow.Height * ((double)bmpSize.Width / bmpSize.Height));
            }
        }

        /// <summary>
        /// 计算画板点和图像点
        /// </summary>
        /// <param name="p">画板点</param>
        private void CalcPoint(Point p)
        {
            m_PbPoint = p;
            m_ImgPoint = new Point((int)((double)m_ImgOriginalSize.Width / pb_ImgShow.Width * p.X),(int)((double)m_ImgOriginalSize.Height / pb_ImgShow.Height * p.Y));
        }

        /// <summary>
        /// 拖拽图片
        /// </summary>
        /// <param name="CurrentPoint"></param>
        private void DragImage(Point CurrentPoint)
        {
            Point offsetPoint = new Point(CurrentPoint.X - m_PbStartPoint.X, CurrentPoint.Y - m_PbStartPoint.Y);
            pb_ImgShow.Location = new Point(pb_ImgShow.Location.X + offsetPoint.X, pb_ImgShow.Location.Y + offsetPoint.Y);
        }

        #endregion

        private void ToolStripMenuItem_GetPoint_Click(object sender, EventArgs e)
        {
            m_MarkPoint = m_ImgPoint;
        }
    }
}
