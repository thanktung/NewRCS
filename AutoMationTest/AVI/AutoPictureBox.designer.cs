namespace SurfDetection
{
    partial class AutoPictureBox
    {
        /// <summary> 
        /// 必需的设计器变量。
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary> 
        /// 清理所有正在使用的资源。
        /// </summary>
        /// <param name="disposing">如果应释放托管资源，为 true；否则为 false。</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region 组件设计器生成的代码

        /// <summary> 
        /// 设计器支持所需的方法 - 不要修改
        /// 使用代码编辑器修改此方法的内容。
        /// </summary>
        private void InitializeComponent()
        {
            this.components = new System.ComponentModel.Container();
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(AutoPictureBox));
            this.pb_ImgShow = new System.Windows.Forms.PictureBox();
            this.contextMenuStrip = new System.Windows.Forms.ContextMenuStrip(this.components);
            this.ToolStripMenuItem_OpenImg = new System.Windows.Forms.ToolStripMenuItem();
            this.toolStripSeparator2 = new System.Windows.Forms.ToolStripSeparator();
            this.ToolStripMenuItem_Selection = new System.Windows.Forms.ToolStripMenuItem();
            this.ToolStripMenuItem_Drag = new System.Windows.Forms.ToolStripMenuItem();
            this.ToolStripMenuItem_Cancel = new System.Windows.Forms.ToolStripMenuItem();
            this.toolStripSeparator1 = new System.Windows.Forms.ToolStripSeparator();
            this.ToolStripMenuItem_RestoreImg = new System.Windows.Forms.ToolStripMenuItem();
            this.ToolStripMenuItem_ClearImg = new System.Windows.Forms.ToolStripMenuItem();
            this.ToolStripMenuItem_SaveImg = new System.Windows.Forms.ToolStripMenuItem();
            this.ToolStripMenuItem_GetPoint = new System.Windows.Forms.ToolStripMenuItem();
            this.statusStrip1 = new System.Windows.Forms.StatusStrip();
            this.tslbl_ScaleMousePos = new System.Windows.Forms.ToolStripStatusLabel();
            this.tslbl_RealMousePos = new System.Windows.Forms.ToolStripStatusLabel();
            this.tslbl_RGBValue = new System.Windows.Forms.ToolStripStatusLabel();
            this.toolStripStatusLabel2 = new System.Windows.Forms.ToolStripStatusLabel();
            ((System.ComponentModel.ISupportInitialize)(this.pb_ImgShow)).BeginInit();
            this.contextMenuStrip.SuspendLayout();
            this.statusStrip1.SuspendLayout();
            this.SuspendLayout();
            // 
            // pb_ImgShow
            // 
            this.pb_ImgShow.BackColor = System.Drawing.Color.Black;
            this.pb_ImgShow.BackgroundImageLayout = System.Windows.Forms.ImageLayout.Stretch;
            this.pb_ImgShow.ContextMenuStrip = this.contextMenuStrip;
            this.pb_ImgShow.Location = new System.Drawing.Point(-4, -26);
            this.pb_ImgShow.Name = "pb_ImgShow";
            this.pb_ImgShow.Size = new System.Drawing.Size(816, 532);
            this.pb_ImgShow.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
            this.pb_ImgShow.TabIndex = 0;
            this.pb_ImgShow.TabStop = false;
            this.pb_ImgShow.MouseDown += new System.Windows.Forms.MouseEventHandler(this.pb_ImShow_MouseDown);
            this.pb_ImgShow.MouseMove += new System.Windows.Forms.MouseEventHandler(this.pb_ImShow_MouseMove);
            this.pb_ImgShow.MouseUp += new System.Windows.Forms.MouseEventHandler(this.pb_ImShow_MouseUp);
            // 
            // contextMenuStrip
            // 
            this.contextMenuStrip.Items.AddRange(new System.Windows.Forms.ToolStripItem[] {
            this.ToolStripMenuItem_OpenImg,
            this.toolStripSeparator2,
            this.ToolStripMenuItem_Selection,
            this.ToolStripMenuItem_Drag,
            this.ToolStripMenuItem_Cancel,
            this.toolStripSeparator1,
            this.ToolStripMenuItem_RestoreImg,
            this.ToolStripMenuItem_ClearImg,
            this.ToolStripMenuItem_SaveImg,
            this.ToolStripMenuItem_GetPoint});
            this.contextMenuStrip.Name = "contextMenuStrip";
            this.contextMenuStrip.Size = new System.Drawing.Size(153, 214);
            // 
            // ToolStripMenuItem_OpenImg
            // 
            this.ToolStripMenuItem_OpenImg.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_OpenImg.Image")));
            this.ToolStripMenuItem_OpenImg.Name = "ToolStripMenuItem_OpenImg";
            this.ToolStripMenuItem_OpenImg.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_OpenImg.Text = "打开图像";
            this.ToolStripMenuItem_OpenImg.Click += new System.EventHandler(this.ToolStripMenuItem_OpenImg_Click);
            // 
            // toolStripSeparator2
            // 
            this.toolStripSeparator2.Name = "toolStripSeparator2";
            this.toolStripSeparator2.Size = new System.Drawing.Size(149, 6);
            // 
            // ToolStripMenuItem_Selection
            // 
            this.ToolStripMenuItem_Selection.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_Selection.Image")));
            this.ToolStripMenuItem_Selection.Name = "ToolStripMenuItem_Selection";
            this.ToolStripMenuItem_Selection.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_Selection.Text = "选框";
            this.ToolStripMenuItem_Selection.Click += new System.EventHandler(this.ToolStripMenuItem_Selection_Click);
            // 
            // ToolStripMenuItem_Drag
            // 
            this.ToolStripMenuItem_Drag.Enabled = false;
            this.ToolStripMenuItem_Drag.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_Drag.Image")));
            this.ToolStripMenuItem_Drag.Name = "ToolStripMenuItem_Drag";
            this.ToolStripMenuItem_Drag.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_Drag.Text = "拖拽";
            this.ToolStripMenuItem_Drag.Click += new System.EventHandler(this.ToolStripMenuItem_Drag_Click);
            // 
            // ToolStripMenuItem_Cancel
            // 
            this.ToolStripMenuItem_Cancel.Enabled = false;
            this.ToolStripMenuItem_Cancel.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_Cancel.Image")));
            this.ToolStripMenuItem_Cancel.Name = "ToolStripMenuItem_Cancel";
            this.ToolStripMenuItem_Cancel.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_Cancel.Text = "取消操作";
            this.ToolStripMenuItem_Cancel.Click += new System.EventHandler(this.ToolStripMenuItem_Cancel_Click);
            // 
            // toolStripSeparator1
            // 
            this.toolStripSeparator1.Name = "toolStripSeparator1";
            this.toolStripSeparator1.Size = new System.Drawing.Size(149, 6);
            // 
            // ToolStripMenuItem_RestoreImg
            // 
            this.ToolStripMenuItem_RestoreImg.Enabled = false;
            this.ToolStripMenuItem_RestoreImg.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_RestoreImg.Image")));
            this.ToolStripMenuItem_RestoreImg.Name = "ToolStripMenuItem_RestoreImg";
            this.ToolStripMenuItem_RestoreImg.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_RestoreImg.Text = "还原图像";
            this.ToolStripMenuItem_RestoreImg.Click += new System.EventHandler(this.ToolStripMenuItem_RestoreImg_Click);
            // 
            // ToolStripMenuItem_ClearImg
            // 
            this.ToolStripMenuItem_ClearImg.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_ClearImg.Image")));
            this.ToolStripMenuItem_ClearImg.Name = "ToolStripMenuItem_ClearImg";
            this.ToolStripMenuItem_ClearImg.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_ClearImg.Text = "清除图像";
            this.ToolStripMenuItem_ClearImg.Click += new System.EventHandler(this.ToolStripMenuItem_ClearImg_Click);
            // 
            // ToolStripMenuItem_SaveImg
            // 
            this.ToolStripMenuItem_SaveImg.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_SaveImg.Image")));
            this.ToolStripMenuItem_SaveImg.Name = "ToolStripMenuItem_SaveImg";
            this.ToolStripMenuItem_SaveImg.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_SaveImg.Text = "保存图像";
            this.ToolStripMenuItem_SaveImg.Click += new System.EventHandler(this.ToolStripMenuItem_SaveImg_Click);
            // 
            // ToolStripMenuItem_GetPoint
            // 
            this.ToolStripMenuItem_GetPoint.Image = ((System.Drawing.Image)(resources.GetObject("ToolStripMenuItem_GetPoint.Image")));
            this.ToolStripMenuItem_GetPoint.Name = "ToolStripMenuItem_GetPoint";
            this.ToolStripMenuItem_GetPoint.Size = new System.Drawing.Size(152, 22);
            this.ToolStripMenuItem_GetPoint.Text = "標定點";
            this.ToolStripMenuItem_GetPoint.Click += new System.EventHandler(this.ToolStripMenuItem_GetPoint_Click);
            // 
            // statusStrip1
            // 
            this.statusStrip1.BackColor = System.Drawing.Color.Black;
            this.statusStrip1.Items.AddRange(new System.Windows.Forms.ToolStripItem[] {
            this.tslbl_ScaleMousePos,
            this.tslbl_RealMousePos,
            this.tslbl_RGBValue,
            this.toolStripStatusLabel2});
            this.statusStrip1.Location = new System.Drawing.Point(0, 510);
            this.statusStrip1.Name = "statusStrip1";
            this.statusStrip1.Size = new System.Drawing.Size(816, 22);
            this.statusStrip1.TabIndex = 93;
            this.statusStrip1.Text = "statusStrip1";
            // 
            // tslbl_ScaleMousePos
            // 
            this.tslbl_ScaleMousePos.BorderSides = System.Windows.Forms.ToolStripStatusLabelBorderSides.Right;
            this.tslbl_ScaleMousePos.ForeColor = System.Drawing.SystemColors.Control;
            this.tslbl_ScaleMousePos.Name = "tslbl_ScaleMousePos";
            this.tslbl_ScaleMousePos.Size = new System.Drawing.Size(4, 17);
            // 
            // tslbl_RealMousePos
            // 
            this.tslbl_RealMousePos.BorderSides = System.Windows.Forms.ToolStripStatusLabelBorderSides.Right;
            this.tslbl_RealMousePos.ForeColor = System.Drawing.SystemColors.Control;
            this.tslbl_RealMousePos.Name = "tslbl_RealMousePos";
            this.tslbl_RealMousePos.Size = new System.Drawing.Size(4, 17);
            // 
            // tslbl_RGBValue
            // 
            this.tslbl_RGBValue.BorderSides = System.Windows.Forms.ToolStripStatusLabelBorderSides.Right;
            this.tslbl_RGBValue.ForeColor = System.Drawing.SystemColors.Control;
            this.tslbl_RGBValue.Name = "tslbl_RGBValue";
            this.tslbl_RGBValue.Size = new System.Drawing.Size(4, 17);
            // 
            // toolStripStatusLabel2
            // 
            this.toolStripStatusLabel2.Name = "toolStripStatusLabel2";
            this.toolStripStatusLabel2.Size = new System.Drawing.Size(789, 17);
            this.toolStripStatusLabel2.Spring = true;
            // 
            // AutoPictureBox
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.BackColor = System.Drawing.Color.Black;
            this.Controls.Add(this.statusStrip1);
            this.Controls.Add(this.pb_ImgShow);
            this.Name = "AutoPictureBox";
            this.Size = new System.Drawing.Size(816, 532);
            this.Load += new System.EventHandler(this.AutoPictureBox_Load);
            this.SizeChanged += new System.EventHandler(this.AutoPictureBox_SizeChanged);
            ((System.ComponentModel.ISupportInitialize)(this.pb_ImgShow)).EndInit();
            this.contextMenuStrip.ResumeLayout(false);
            this.statusStrip1.ResumeLayout(false);
            this.statusStrip1.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        public System.Windows.Forms.PictureBox pb_ImgShow;
        private System.Windows.Forms.ContextMenuStrip contextMenuStrip;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_Selection;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_Drag;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_OpenImg;
        private System.Windows.Forms.ToolStripSeparator toolStripSeparator2;
        private System.Windows.Forms.ToolStripSeparator toolStripSeparator1;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_RestoreImg;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_Cancel;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_ClearImg;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_SaveImg;
        private System.Windows.Forms.StatusStrip statusStrip1;
        private System.Windows.Forms.ToolStripStatusLabel tslbl_ScaleMousePos;
        private System.Windows.Forms.ToolStripStatusLabel tslbl_RealMousePos;
        private System.Windows.Forms.ToolStripStatusLabel tslbl_RGBValue;
        private System.Windows.Forms.ToolStripStatusLabel toolStripStatusLabel2;
        private System.Windows.Forms.ToolStripMenuItem ToolStripMenuItem_GetPoint;
    }
}
