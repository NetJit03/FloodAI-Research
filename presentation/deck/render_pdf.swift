import AppKit
import PDFKit
import Foundation

guard CommandLine.arguments.count == 3 else {
    fputs("Usage: render_pdf.swift input.pdf output_directory\n", stderr)
    exit(2)
}
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
guard let document = PDFDocument(url: input) else { fatalError("Cannot read PDF") }
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { fatalError("Missing page") }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 1.6
    let width = Int(bounds.width * scale)
    let height = Int(bounds.height * scale)
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    guard let ctx = CGContext(data:nil, width:width, height:height, bitsPerComponent:8,
                              bytesPerRow:0, space:colorSpace,
                              bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue) else { fatalError("Cannot create context") }
    ctx.setFillColor(CGColor.white)
    ctx.fill(CGRect(x:0,y:0,width:width,height:height))
    ctx.scaleBy(x:scale,y:scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let cg = ctx.makeImage() else { fatalError("Cannot create image") }
    let bitmap = NSBitmapImageRep(cgImage:cg)
    guard let png = bitmap.representation(using:.png, properties:[:]) else { fatalError("Cannot encode PNG") }
    let name = String(format:"slide-%02d.png",index+1)
    try png.write(to: output.appendingPathComponent(name))
}
print("Rendered \(document.pageCount) pages")
