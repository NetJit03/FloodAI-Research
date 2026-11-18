#import <AppKit/AppKit.h>
#import <PDFKit/PDFKit.h>

int main(int argc, const char *argv[]) {
  @autoreleasepool {
    if (argc != 3) { fprintf(stderr,"Usage: render_pdf input.pdf output_dir\n"); return 2; }
    NSString *inpath=[NSString stringWithUTF8String:argv[1]];
    NSString *outpath=[NSString stringWithUTF8String:argv[2]];
    [[NSFileManager defaultManager] createDirectoryAtPath:outpath withIntermediateDirectories:YES attributes:nil error:nil];
    PDFDocument *doc=[[PDFDocument alloc] initWithURL:[NSURL fileURLWithPath:inpath]];
    if (!doc) { fprintf(stderr,"Cannot open PDF\n"); return 1; }
    for (NSUInteger i=0;i<doc.pageCount;i++) {
      @autoreleasepool {
        PDFPage *page=[doc pageAtIndex:i];
        CGRect bounds=[page boundsForBox:kPDFDisplayBoxMediaBox];
        CGFloat scale=1.6;
        size_t width=(size_t)(bounds.size.width*scale),height=(size_t)(bounds.size.height*scale);
        CGColorSpaceRef space=CGColorSpaceCreateDeviceRGB();
        CGContextRef ctx=CGBitmapContextCreate(NULL,width,height,8,0,space,kCGImageAlphaPremultipliedLast);
        CGColorSpaceRelease(space);
        if (!ctx) { fprintf(stderr,"Cannot allocate bitmap\n"); return 1; }
        CGContextSetRGBFillColor(ctx,1,1,1,1);
        CGContextFillRect(ctx,CGRectMake(0,0,width,height));
        CGContextScaleCTM(ctx,scale,scale);
        [page drawWithBox:kPDFDisplayBoxMediaBox toContext:ctx];
        CGImageRef image=CGBitmapContextCreateImage(ctx);
        NSBitmapImageRep *bitmap=[[NSBitmapImageRep alloc] initWithCGImage:image];
        NSData *png=[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        NSString *filename=[NSString stringWithFormat:@"slide-%02lu.png",(unsigned long)i+1];
        if (![png writeToFile:[outpath stringByAppendingPathComponent:filename] atomically:YES]) {
          fprintf(stderr,"Cannot write PNG\n"); return 1;
        }
        CGImageRelease(image); CGContextRelease(ctx);
      }
    }
    printf("Rendered %lu pages\n",(unsigned long)doc.pageCount);
  }
  return 0;
}
